MH4 HTTP Auto Move 便携版
=========================

目标电脑不需要安装 Python。

下载/克隆后先合并分片
-----------------------
Ubuntu：

  cat ubuntu-x86_64.zip.part-* > ubuntu-x86_64.zip

Windows CMD：

  copy /b windows-x64.zip.part-* windows-x64.zip

合并后可根据 SHA256SUMS.txt 校验完整 zip；SHA256SUMS.parts.txt 用于校验各分片。

Ubuntu 22.04/24.04 x86_64
--------------------------
合并并完整解压 ubuntu-x86_64.zip 后运行：

  ./启动_MH4_HTTP_Auto_Move.sh

Windows 10/11 x64
-----------------
合并并完整解压 windows-x64.zip 后，双击“MH4_HTTP_Auto_Move.exe”。
也可以双击“启动_MH4_HTTP_Auto_Move.cmd”，效果相同。
如程序没有显示，运行“诊断启动.cmd”查看错误信息。

注意
----
1. 3D 轨迹依赖 OpenGL 和显卡驱动。
2. 不要直接在压缩软件的预览窗口中运行。
3. 连接机器人前，请确保网络互通并保留现场急停措施。
