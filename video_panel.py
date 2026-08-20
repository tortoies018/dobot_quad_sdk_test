"""Two-view wireless camera panel for the MH4 robot."""

from __future__ import annotations

from PySide6.QtCore import Qt, QTimer, QUrl, Signal
from PySide6.QtMultimedia import QMediaPlayer
from PySide6.QtMultimediaWidgets import QVideoWidget
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
RTSP_PORT = 8554


def video_stream_url(host: str, stream_name: str) -> QUrl:
    """Build the robot's built-in wireless RTSP URL."""

    clean_host = host.strip().strip("[]")
    if not clean_host:
        raise ValueError("图传主机不能为空")
    if stream_name not in {name for _label, name in VIDEO_STREAMS}:
        raise ValueError(f"不支持的图传名称: {stream_name}")
    url_host = f"[{clean_host}]" if ":" in clean_host else clean_host
    return QUrl(f"rtsp://{url_host}:{RTSP_PORT}/{stream_name}")


class HttpVideoTile(QFrame):
    """One asynchronous QMediaPlayer surface with a compact status line."""

    def __init__(self, title: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
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

        self.video_widget = QVideoWidget()
        self.video_widget.setAspectRatioMode(Qt.KeepAspectRatio)
        self.video_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.video_widget.setMinimumSize(240, 160)
        self.video_widget.setStyleSheet("background:#000; border:none;")
        layout.addWidget(self.video_widget, 1)

        self.status_label = QLabel("等待 HTTP 连接")
        self.status_label.setStyleSheet("color:#a8b3bc; font:11px monospace;")
        layout.addWidget(self.status_label)

        self.player = QMediaPlayer(self)
        self.player.setVideoOutput(self.video_widget)
        self.player.playbackStateChanged.connect(self._on_playback_state)
        self.player.mediaStatusChanged.connect(self._on_media_status)
        self.player.errorOccurred.connect(self._on_error)

    def configure(self, url: QUrl) -> None:
        self.player.stop()
        if self.player.source() == url:
            self.player.setSource(QUrl())
        self.player.setSource(url)
        self._set_status("等待图传启动", "#a8b3bc")

    def play(self) -> None:
        if not self.player.source().isEmpty():
            self._set_status("正在连接无线视频…", "#80cbc4")
            self.player.play()

    def stop(self, *, clear_source: bool = False) -> None:
        self.player.stop()
        if clear_source:
            self.player.setSource(QUrl())
        self._set_status("已停止", "#a8b3bc")

    def _set_status(self, text: str, colour: str) -> None:
        self.status_label.setText(text)
        self.status_label.setStyleSheet(f"color:{colour}; font:11px monospace;")

    def _on_playback_state(self, state: QMediaPlayer.PlaybackState) -> None:
        if state == QMediaPlayer.PlayingState:
            self._set_status("播放中", "#69f0ae")
        elif state == QMediaPlayer.PausedState:
            self._set_status("已暂停", "#ffcc80")

    def _on_media_status(self, status: QMediaPlayer.MediaStatus) -> None:
        if status in (QMediaPlayer.LoadingMedia, QMediaPlayer.BufferingMedia):
            self._set_status("正在缓冲…", "#80cbc4")
        elif status == QMediaPlayer.StalledMedia:
            self._set_status("视频数据暂时中断", "#ffcc80")
        elif status == QMediaPlayer.InvalidMedia:
            self._set_status("无法打开无线视频", "#ff8a80")
        elif (
            status in (QMediaPlayer.LoadedMedia, QMediaPlayer.BufferedMedia)
            and self.player.playbackState() == QMediaPlayer.PlayingState
        ):
            self._set_status("播放中", "#69f0ae")

    def _on_error(self, _error: QMediaPlayer.Error, message: str) -> None:
        detail = message.strip() or "未知播放器错误"
        self._set_status(f"播放失败：{detail}", "#ff8a80")


class TwoVideoPanel(QWidget):
    """Front/rear video tab; HTTP controls producers and RTSP carries frames."""

    restart_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._host = ""
        self._urls: list[QUrl] = []
        self._streaming_ready = False
        self._retry_timer = QTimer(self)
        self._retry_timer.setInterval(2000)
        self._retry_timer.timeout.connect(self._retry_unavailable)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(7, 7, 7, 7)
        layout.setSpacing(6)

        header = QHBoxLayout()
        self.summary_label = QLabel(
            "前后双路无线画面；连接机器人后自动启动（不使用 DDS）"
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
        self.tiles: list[HttpVideoTile] = []
        for column, (label, _stream_name) in enumerate(VIDEO_STREAMS):
            tile = HttpVideoTile(label)
            self.tiles.append(tile)
            grid.addWidget(tile, 0, column)
            grid.setColumnStretch(column, 1)
        grid.setRowStretch(0, 1)
        layout.addLayout(grid, 1)

    def configure_host(self, host: str) -> None:
        self._host = host.strip().strip("[]")
        self._streaming_ready = False
        self._retry_timer.stop()
        self._urls = [
            video_stream_url(self._host, stream_name)
            for _label, stream_name in VIDEO_STREAMS
        ]
        # setSource 会立即探测 RTSP；先等 HTTP /streaming/start 成功，避免抢跑。
        for tile in self.tiles:
            tile.stop(clear_source=True)
        self.summary_label.setText("正在通过 HTTP 启动前后图传…")
        self.summary_label.setStyleSheet("color:#80cbc4;")
        self.restart_button.setEnabled(True)

    def set_streaming_result(self, ok: bool, message: str) -> None:
        self._streaming_ready = ok
        self.summary_label.setText(
            f"{message}，正在等待视频流就绪…" if ok else message
        )
        self.summary_label.setStyleSheet(
            "color:#69f0ae;" if ok else "color:#ff8a80;"
        )
        if ok:
            # 控制器先确认 HTTP 请求，相机生产者稍后才注册到 RTSP 服务。
            QTimer.singleShot(750, self._start_players)
            self._retry_timer.start()
        else:
            self._retry_timer.stop()
            for tile in self.tiles:
                tile.stop()

    def _start_players(self) -> None:
        if not self._streaming_ready:
            return
        for tile, url in zip(self.tiles, self._urls):
            if tile.player.playbackState() == QMediaPlayer.PlayingState:
                continue
            tile.configure(url)
            tile.play()

    def _retry_unavailable(self) -> None:
        if not self._streaming_ready:
            return
        if all(
            tile.player.playbackState() == QMediaPlayer.PlayingState
            for tile in self.tiles
        ):
            self.summary_label.setText(
                "前后无线视频播放中（camera1 / camera2）"
            )
            self.summary_label.setStyleSheet("color:#69f0ae;")
            return
        retryable = {
            QMediaPlayer.NoMedia,
            QMediaPlayer.EndOfMedia,
            QMediaPlayer.InvalidMedia,
        }
        for tile, url in zip(self.tiles, self._urls):
            if tile.player.playbackState() == QMediaPlayer.PlayingState:
                continue
            if (
                tile.player.mediaStatus() in retryable
                or tile.player.error() != QMediaPlayer.NoError
            ):
                self.summary_label.setText("视频尚未就绪，正在自动重连…")
                self.summary_label.setStyleSheet("color:#ffcc80;")
                tile.configure(url)
                tile.play()

    def _request_restart(self) -> None:
        if not self._host:
            return
        self._streaming_ready = False
        self._retry_timer.stop()
        for tile in self.tiles:
            tile.stop(clear_source=True)
        self.summary_label.setText("正在重新启动 HTTP 图传…")
        self.summary_label.setStyleSheet("color:#80cbc4;")
        self.restart_requested.emit()

    def stop(self) -> None:
        self._streaming_ready = False
        self._retry_timer.stop()
        for tile in self.tiles:
            tile.stop()
        self.summary_label.setText("HTTP 连接已关闭，视频已停止")
        self.summary_label.setStyleSheet("color:#a8b3bc;")
        self.restart_button.setEnabled(False)

    def shutdown(self) -> None:
        self._streaming_ready = False
        self._retry_timer.stop()
        for tile in self.tiles:
            tile.stop(clear_source=True)
        self._host = ""
        self._urls.clear()
        self.restart_button.setEnabled(False)
