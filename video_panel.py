"""Native low-latency WebRTC panel for the MH4 front and rear cameras."""

from __future__ import annotations

import asyncio
import ssl
import threading
import time
from urllib.parse import urlencode
from urllib.request import HTTPSHandler, ProxyHandler, Request, build_opener

from PySide6.QtCore import QObject, Qt, QTimer, Signal
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)


VIDEO_STREAMS = (("前置画面", "camera1"), ("后置画面", "camera2"))


def _stream_name(stream_name: str) -> str:
    if stream_name not in {name for _label, name in VIDEO_STREAMS}:
        raise ValueError(f"不支持的图传名称: {stream_name}")
    return stream_name


def _url_host(host: str) -> str:
    clean_host = host.strip().strip("[]")
    if not clean_host:
        raise ValueError("图传主机不能为空")
    return f"[{clean_host}]" if ":" in clean_host else clean_host


def webrtc_offer_url(host: str, stream_name: str) -> str:
    """Return the robot go2rtc WHEP endpoint for one named camera."""

    return (
        f"https://{_url_host(host)}/api/webrtc?"
        f"{urlencode({'src': _stream_name(stream_name)})}"
    )


def _robot_tls_context() -> ssl.SSLContext:
    """Create a TLS context for the robot's local self-signed certificate."""

    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    return context


def _post_webrtc_offer(
    host: str,
    stream_name: str,
    offer_sdp: str,
    timeout: float = 8.0,
) -> str:
    """Exchange one SDP offer with go2rtc without using desktop proxies."""

    request = Request(
        webrtc_offer_url(host, stream_name),
        data=offer_sdp.encode("utf-8"),
        headers={
            "Accept": "application/sdp",
            "Content-Type": "application/sdp",
        },
        method="POST",
    )
    opener = build_opener(
        ProxyHandler({}), HTTPSHandler(context=_robot_tls_context())
    )
    with opener.open(request, timeout=timeout) as response:
        answer = response.read().decode("utf-8")
    if not answer.lstrip().startswith("v=0"):
        raise RuntimeError("WebRTC 信令没有返回有效 SDP")
    return answer


class NativeWebRtcReceiver(QObject):
    """Receive two H.264 WebRTC streams on background asyncio threads."""

    status_changed = Signal(str, bool, str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._lock = threading.Lock()
        self._generation = 0
        self._stop_event: threading.Event | None = None
        self._threads: list[threading.Thread] = []
        self._latest_frames: dict[str, QImage] = {}
        self._frame_counts = {stream: 0 for _label, stream in VIDEO_STREAMS}

    def start(self, host: str) -> None:
        # 重连时只发停止信号，不在 GUI 线程等待旧网络请求超时。
        self.stop(wait=False)
        stop_event = threading.Event()
        with self._lock:
            previous_threads = [
                thread for thread in self._threads if thread.is_alive()
            ]
            self._generation += 1
            generation = self._generation
            self._stop_event = stop_event
            self._latest_frames.clear()
            self._frame_counts = {
                stream: 0 for _label, stream in VIDEO_STREAMS
            }

        threads = [
            threading.Thread(
                target=self._thread_main,
                args=(host, stream_name, generation, stop_event),
                name=f"mh4-webrtc-{stream_name}",
                daemon=True,
            )
            for _label, stream_name in VIDEO_STREAMS
        ]
        with self._lock:
            if generation != self._generation:
                return
            self._threads = previous_threads + threads
        for thread in threads:
            thread.start()

    def stop(self, *, wait: bool = False) -> None:
        with self._lock:
            self._generation += 1
            stop_event = self._stop_event
            threads = list(self._threads)
            self._stop_event = None
            self._latest_frames.clear()
        if stop_event is not None:
            stop_event.set()
        if wait:
            deadline = time.monotonic() + 9.0
            for thread in threads:
                remaining = max(0.0, deadline - time.monotonic())
                thread.join(timeout=remaining)
        with self._lock:
            self._threads = [thread for thread in threads if thread.is_alive()]

    def take_frame(self, stream_name: str) -> QImage | None:
        with self._lock:
            return self._latest_frames.pop(stream_name, None)

    def frame_counts(self) -> dict[str, int]:
        with self._lock:
            return dict(self._frame_counts)

    def _is_current(
        self, generation: int, stop_event: threading.Event
    ) -> bool:
        with self._lock:
            return generation == self._generation and not stop_event.is_set()

    def _emit_status(
        self,
        generation: int,
        stop_event: threading.Event,
        stream_name: str,
        ok: bool,
        message: str,
    ) -> None:
        if self._is_current(generation, stop_event):
            self.status_changed.emit(stream_name, ok, message)

    def _thread_main(
        self,
        host: str,
        stream_name: str,
        generation: int,
        stop_event: threading.Event,
    ) -> None:
        try:
            from aiortc import (
                RTCPeerConnection,
                RTCRtpReceiver,
                RTCSessionDescription,
            )
            from aiortc.mediastreams import MediaStreamError
        except Exception as exc:
            self._emit_status(
                generation,
                stop_event,
                stream_name,
                False,
                f"缺少 WebRTC 运行库: {exc}",
            )
            return

        try:
            asyncio.run(
                self._stream_loop(
                    host,
                    stream_name,
                    generation,
                    stop_event,
                    RTCPeerConnection,
                    RTCRtpReceiver,
                    RTCSessionDescription,
                    MediaStreamError,
                )
            )
        except Exception as exc:
            self._emit_status(
                generation,
                stop_event,
                stream_name,
                False,
                f"WebRTC 后台异常: {exc}",
            )

    async def _stream_loop(
        self,
        host: str,
        stream_name: str,
        generation: int,
        stop_event: threading.Event,
        peer_connection_type,
        receiver_type,
        session_description_type,
        media_stream_error_type,
    ) -> None:
        while self._is_current(generation, stop_event):
            self._emit_status(
                generation,
                stop_event,
                stream_name,
                False,
                "正在连接 WebRTC…",
            )
            try:
                await self._receive_once(
                    host,
                    stream_name,
                    generation,
                    stop_event,
                    peer_connection_type,
                    receiver_type,
                    session_description_type,
                    media_stream_error_type,
                )
            except asyncio.CancelledError:
                return
            except Exception as exc:
                if not self._is_current(generation, stop_event):
                    return
                self._emit_status(
                    generation,
                    stop_event,
                    stream_name,
                    False,
                    f"WebRTC 中断，2 秒后重连: {exc}",
                )
            for _index in range(20):
                if not self._is_current(generation, stop_event):
                    return
                await asyncio.sleep(0.1)

    async def _receive_once(
        self,
        host: str,
        stream_name: str,
        generation: int,
        stop_event: threading.Event,
        peer_connection_type,
        receiver_type,
        session_description_type,
        media_stream_error_type,
    ) -> None:
        connection = peer_connection_type()
        tracks: asyncio.Queue = asyncio.Queue(maxsize=1)

        @connection.on("track")
        def on_track(track) -> None:
            if track.kind == "video" and tracks.empty():
                tracks.put_nowait(track)

        try:
            transceiver = connection.addTransceiver("video", direction="recvonly")
            h264_codecs = [
                codec
                for codec in receiver_type.getCapabilities("video").codecs
                if codec.mimeType.lower() == "video/h264"
            ]
            if not h264_codecs:
                raise RuntimeError("本机 WebRTC 不支持 H.264")
            transceiver.setCodecPreferences(h264_codecs)

            offer = await connection.createOffer()
            await connection.setLocalDescription(offer)
            answer_sdp = _post_webrtc_offer(
                host, stream_name, connection.localDescription.sdp
            )
            answer = session_description_type(sdp=answer_sdp, type="answer")
            await connection.setRemoteDescription(answer)
            track = await asyncio.wait_for(tracks.get(), timeout=8.0)

            first_frame = True
            while self._is_current(generation, stop_event):
                try:
                    frame = await asyncio.wait_for(track.recv(), timeout=2.0)
                except media_stream_error_type as exc:
                    raise RuntimeError("视频轨道已结束") from exc
                # aiortc 的远端轨道队列可能在图像转换期间积帧；在转换前排空队列，
                # 只显示最新的解码帧，慢机器上也不会越播越落后。
                frame_queue = getattr(track, "_queue", None)
                if isinstance(frame_queue, asyncio.Queue):
                    while True:
                        try:
                            newer_frame = frame_queue.get_nowait()
                        except asyncio.QueueEmpty:
                            break
                        if newer_frame is None:
                            raise RuntimeError("视频轨道已结束")
                        frame = newer_frame
                image = self._frame_to_image(frame)
                with self._lock:
                    if generation != self._generation or stop_event.is_set():
                        return
                    # 只保留最新帧；GUI 变慢时直接覆盖旧帧，延迟不会累积。
                    self._latest_frames[stream_name] = image
                    self._frame_counts[stream_name] += 1
                if first_frame:
                    first_frame = False
                    self._emit_status(
                        generation,
                        stop_event,
                        stream_name,
                        True,
                        f"WebRTC 播放中 {frame.width}×{frame.height}",
                    )
        finally:
            await connection.close()

    @staticmethod
    def _frame_to_image(frame) -> QImage:
        rgb = frame.to_ndarray(format="rgb24")
        image = QImage(
            rgb.data,
            frame.width,
            frame.height,
            int(rgb.strides[0]),
            QImage.Format_RGB888,
        )
        return image.copy()


class WebRtcVideoTile(QFrame):
    """One image surface fed by the native WebRTC receiver."""

    def __init__(self, title: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._last_frame: QImage | None = None
        self.setFrameShape(QFrame.StyledPanel)
        self.setStyleSheet(
            "QFrame { background:#25272b; border:1px solid #4f5359; }"
            "QLabel { border:none; }"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(4)
        self.title_label = QLabel(title)
        self.title_label.setStyleSheet("color:#e5e7eb; font-weight:bold;")
        layout.addWidget(self.title_label)

        self.image_label = QLabel("等待 HTTP 连接")
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.image_label.setMinimumSize(240, 160)
        self.image_label.setStyleSheet("background:#000; color:#777; border:none;")
        layout.addWidget(self.image_label, 1)

        self.status_label = QLabel("未连接")
        self.status_label.setStyleSheet("color:#a8b3bc; font:11px monospace;")
        layout.addWidget(self.status_label)

    def set_status(self, text: str, colour: str) -> None:
        self.status_label.setText(text)
        self.status_label.setStyleSheet(f"color:{colour}; font:11px monospace;")

    def set_frame(self, image: QImage) -> None:
        self._last_frame = image
        self.image_label.setText("")
        self._draw_frame()

    def clear_frame(self, text: str = "等待 WebRTC 视频") -> None:
        self._last_frame = None
        self.image_label.clear()
        self.image_label.setText(text)

    def resizeEvent(self, event) -> None:  # noqa: N802 - Qt API
        super().resizeEvent(event)
        self._draw_frame()

    def _draw_frame(self) -> None:
        if self._last_frame is None or self.image_label.size().isEmpty():
            return
        pixmap = QPixmap.fromImage(self._last_frame).scaled(
            self.image_label.size(),
            Qt.KeepAspectRatio,
            Qt.FastTransformation,
        )
        self.image_label.setPixmap(pixmap)


class TwoVideoPanel(QWidget):
    """Front/rear native WebRTC tab controlled by the HTTP connection."""

    restart_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._host = ""
        self._streaming_ready = False
        self._active_streams: set[str] = set()

        self.receiver = NativeWebRtcReceiver(self)
        self.receiver.status_changed.connect(self._on_stream_status)
        self._render_timer = QTimer(self)
        self._render_timer.setInterval(33)
        self._render_timer.timeout.connect(self._render_latest_frames)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(7, 7, 7, 7)
        layout.setSpacing(6)

        header = QHBoxLayout()
        self.summary_label = QLabel(
            "前后双路无线 WebRTC；连接机器人后自动启动（不使用 DDS）"
        )
        self.summary_label.setStyleSheet("color:#a8b3bc;")
        header.addWidget(self.summary_label, 1)
        self.restart_button = QPushButton("重新连接视频")
        self.restart_button.setEnabled(False)
        self.restart_button.setStyleSheet(
            "QPushButton { background:#455a64; color:white; border:none; "
            "border-radius:4px; padding:6px 12px; }"
            "QPushButton:hover { background:#607d8b; }"
            "QPushButton:disabled { background:#3b3d42; color:#777; }"
        )
        self.restart_button.clicked.connect(self._request_restart)
        header.addWidget(self.restart_button)
        layout.addLayout(header)

        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(7)
        self.tiles: dict[str, WebRtcVideoTile] = {}
        for column, (label, stream_name) in enumerate(VIDEO_STREAMS):
            tile = WebRtcVideoTile(label)
            self.tiles[stream_name] = tile
            grid.addWidget(tile, 0, column)
            grid.setColumnStretch(column, 1)
        grid.setRowStretch(0, 1)
        layout.addLayout(grid, 1)

    def configure_host(self, host: str) -> None:
        clean_host = host.strip().strip("[]")
        for _label, stream_name in VIDEO_STREAMS:
            webrtc_offer_url(clean_host, stream_name)
        self._host = clean_host
        self._streaming_ready = False
        self._active_streams.clear()
        self.receiver.stop()
        self._render_timer.stop()
        for tile in self.tiles.values():
            tile.clear_frame()
            tile.set_status("等待 HTTP 图传启动", "#a8b3bc")
        self.summary_label.setText("正在通过 HTTP 启动前后图传…")
        self.summary_label.setStyleSheet("color:#80cbc4;")
        self.restart_button.setEnabled(True)

    def set_streaming_result(self, ok: bool, message: str) -> None:
        self._streaming_ready = ok
        if not ok:
            self.receiver.stop()
            self._render_timer.stop()
            self.summary_label.setText(message)
            self.summary_label.setStyleSheet("color:#ff8a80;")
            for tile in self.tiles.values():
                tile.set_status("HTTP 图传启动失败", "#ff8a80")
            return
        self.summary_label.setText(f"{message}，正在建立 WebRTC…")
        self.summary_label.setStyleSheet("color:#80cbc4;")
        # HTTP 成功早于相机生产者就绪，稍等后再交换 WebRTC SDP。
        QTimer.singleShot(1500, self._start_receiver)

    def _start_receiver(self) -> None:
        if not self._streaming_ready or not self._host:
            return
        self._active_streams.clear()
        self.receiver.start(self._host)
        self._render_timer.start()

    def _on_stream_status(
        self, stream_name: str, ok: bool, message: str
    ) -> None:
        tile = self.tiles.get(stream_name)
        if tile is None:
            return
        if ok:
            self._active_streams.add(stream_name)
            tile.set_status(message, "#69f0ae")
            if len(self._active_streams) == len(VIDEO_STREAMS):
                self.summary_label.setText(
                    "前后无线 WebRTC 播放中（低延迟、自动丢弃积压帧）"
                )
                self.summary_label.setStyleSheet("color:#69f0ae;")
        else:
            self._active_streams.discard(stream_name)
            tile.set_status(message, "#ffcc80")
            if "正在连接" not in message:
                tile.clear_frame("WebRTC 正在重连")
            self.summary_label.setText(message)
            self.summary_label.setStyleSheet("color:#ffcc80;")

    def _render_latest_frames(self) -> None:
        for _label, stream_name in VIDEO_STREAMS:
            image = self.receiver.take_frame(stream_name)
            if image is not None:
                self.tiles[stream_name].set_frame(image)

    def _request_restart(self) -> None:
        if not self._host:
            return
        self._streaming_ready = False
        self._active_streams.clear()
        self.receiver.stop()
        self._render_timer.stop()
        for tile in self.tiles.values():
            tile.clear_frame()
            tile.set_status("正在重新连接", "#80cbc4")
        self.summary_label.setText("正在重新启动 HTTP 图传…")
        self.summary_label.setStyleSheet("color:#80cbc4;")
        self.restart_requested.emit()

    def stop(self) -> None:
        self._streaming_ready = False
        self._active_streams.clear()
        self.receiver.stop()
        self._render_timer.stop()
        for tile in self.tiles.values():
            tile.clear_frame("HTTP 连接已关闭")
            tile.set_status("已停止", "#a8b3bc")
        self.summary_label.setText("HTTP 连接已关闭，WebRTC 已停止")
        self.summary_label.setStyleSheet("color:#a8b3bc;")
        self.restart_button.setEnabled(False)

    def shutdown(self) -> None:
        self._streaming_ready = False
        self._render_timer.stop()
        self.receiver.stop(wait=True)
        self._host = ""
        self.restart_button.setEnabled(False)
