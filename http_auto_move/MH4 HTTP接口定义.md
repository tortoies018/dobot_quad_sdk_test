# MH4 HTTP接口定义

*   [1. 修订记录](#1-%E4%BF%AE%E8%AE%A2%E8%AE%B0%E5%BD%95)
    
*   [2. 接口设计思想](#2-%E6%8E%A5%E5%8F%A3%E8%AE%BE%E8%AE%A1%E6%80%9D%E6%83%B3)
    
*   [3. MH4接口](#3-mh4%E6%8E%A5%E5%8F%A3)
    
    *   [3.1. 接口地址和端口](#31-%E6%8E%A5%E5%8F%A3%E5%9C%B0%E5%9D%80%E5%92%8C%E7%AB%AF%E5%8F%A3)
        
    *   [3.2. 设备连接（/connection）](#32-%E8%AE%BE%E5%A4%87%E8%BF%9E%E6%8E%A5connection)
        
        *   [3.2.1. 连接](#321-%E8%BF%9E%E6%8E%A5)
            
        *   [3.2.2. 连接方式](#322-%E8%BF%9E%E6%8E%A5%E6%96%B9%E5%BC%8F)
            
    *   [3.3. 周期协议（/protocol）](#33-%E5%91%A8%E6%9C%9F%E5%8D%8F%E8%AE%AEprotocol)
        
        *   [3.3.1. exchange](#331-exchange)
            
    *   [3.4. 参数设置（/settings）](#34-%E5%8F%82%E6%95%B0%E8%AE%BE%E7%BD%AEsettings)
        
        *   [3.4.1. 版本信息](#341-%E7%89%88%E6%9C%AC%E4%BF%A1%E6%81%AF)
            
        *   [3.4.2. 报警清除](#342-%E6%8A%A5%E8%AD%A6%E6%B8%85%E9%99%A4)
            
        *   [3.4.3. 位置超限数据获取设置](#343-%E4%BD%8D%E7%BD%AE%E8%B6%85%E9%99%90%E6%95%B0%E6%8D%AE%E8%8E%B7%E5%8F%96%E8%AE%BE%E7%BD%AE)
            
        *   [3.4.4. 速度超限数据获取设置](#344-%E9%80%9F%E5%BA%A6%E8%B6%85%E9%99%90%E6%95%B0%E6%8D%AE%E8%8E%B7%E5%8F%96%E8%AE%BE%E7%BD%AE)
            
        *   [3.4.5. 力矩超限数据获取设置](#345-%E5%8A%9B%E7%9F%A9%E8%B6%85%E9%99%90%E6%95%B0%E6%8D%AE%E8%8E%B7%E5%8F%96%E8%AE%BE%E7%BD%AE)
            
        *   [3.4.6. KP超限数据获取设置](#346-kp%E8%B6%85%E9%99%90%E6%95%B0%E6%8D%AE%E8%8E%B7%E5%8F%96%E8%AE%BE%E7%BD%AE)
            
        *   [3.4.7. KD超限数据获取设置](#347-kd%E8%B6%85%E9%99%90%E6%95%B0%E6%8D%AE%E8%8E%B7%E5%8F%96%E8%AE%BE%E7%BD%AE)
            
        *   [3.4.8. 急停](#348-%E6%80%A5%E5%81%9C)
            
        *   [3.4.9. 摇杆控制](#349-%E6%91%87%E6%9D%86%E6%8E%A7%E5%88%B6)
            
        *   [3.4.10. 获取常用动作和姿势](#3410-%E8%8E%B7%E5%8F%96%E5%B8%B8%E7%94%A8%E5%8A%A8%E4%BD%9C%E5%92%8C%E5%A7%BF%E5%8A%BF)
            
        *   [3.4.11. 执行常用动作和姿势](#3411-%E6%89%A7%E8%A1%8C%E5%B8%B8%E7%94%A8%E5%8A%A8%E4%BD%9C%E5%92%8C%E5%A7%BF%E5%8A%BF)
            
        *   [3.4.12. 动作执行参数](#3412-%E5%8A%A8%E4%BD%9C%E6%89%A7%E8%A1%8C%E5%8F%82%E6%95%B0)
            
        *   [3.4.13. 高危动作协议申请](#3413-%E9%AB%98%E5%8D%B1%E5%8A%A8%E4%BD%9C%E5%8D%8F%E8%AE%AE%E7%94%B3%E8%AF%B7)
            
        *   [3.4.14. 图传-通知机器狗开启中转服务器（AP模式）和socket连接](#3414-%E5%9B%BE%E4%BC%A0-%E9%80%9A%E7%9F%A5%E6%9C%BA%E5%99%A8%E7%8B%97%E5%BC%80%E5%90%AF%E4%B8%AD%E8%BD%AC%E6%9C%8D%E5%8A%A1%E5%99%A8ap%E6%A8%A1%E5%BC%8F%E5%92%8Csocket%E8%BF%9E%E6%8E%A5)
            
        *   [3.4.15. 图传-停止图传](#3415-%E5%9B%BE%E4%BC%A0-%E5%81%9C%E6%AD%A2%E5%9B%BE%E4%BC%A0)
            
        *   [3.4.16. 图传-视频录制](#3416-%E5%9B%BE%E4%BC%A0-%E8%A7%86%E9%A2%91%E5%BD%95%E5%88%B6)
            
        *   [3.4.17. 图传-录制视频下载](#3417-%E5%9B%BE%E4%BC%A0-%E5%BD%95%E5%88%B6%E8%A7%86%E9%A2%91%E4%B8%8B%E8%BD%BD)
            
        *   [3.4.18. 检查更新](#3418-%E6%A3%80%E6%9F%A5%E6%9B%B4%E6%96%B0)
            
        *   [3.4.19. 判断安装包是否已经下载](#3419-%E5%88%A4%E6%96%AD%E5%AE%89%E8%A3%85%E5%8C%85%E6%98%AF%E5%90%A6%E5%B7%B2%E7%BB%8F%E4%B8%8B%E8%BD%BD)
            
        *   [3.4.20. 下载OTA升级包](#3420-%E4%B8%8B%E8%BD%BDota%E5%8D%87%E7%BA%A7%E5%8C%85)
            
        *   [3.4.21. 通知OTA升级](#3421-%E9%80%9A%E7%9F%A5ota%E5%8D%87%E7%BA%A7)
            
        *   [3.4.22. OTA包下载进度](#3422-ota%E5%8C%85%E4%B8%8B%E8%BD%BD%E8%BF%9B%E5%BA%A6)
            
        *   [3.4.23. OTA包校验](#3423-ota%E5%8C%85%E6%A0%A1%E9%AA%8C)
            
        *   [3.4.24. OTA包升级进度](#3424-ota%E5%8C%85%E5%8D%87%E7%BA%A7%E8%BF%9B%E5%BA%A6)
            
        *   [3.4.25. 探照灯开关](#3425-%E6%8E%A2%E7%85%A7%E7%81%AF%E5%BC%80%E5%85%B3)
            
        *   [3.4.26. 语言设置](#3426-%E8%AF%AD%E8%A8%80%E8%AE%BE%E7%BD%AE)
            
        *   [3.4.27. uid获取及设置](#3427-uid%E8%8E%B7%E5%8F%96%E5%8F%8A%E8%AE%BE%E7%BD%AE)
            
        *   [3.4.28. 系统时间设置/获取](#3428-%E7%B3%BB%E7%BB%9F%E6%97%B6%E9%97%B4%E8%AE%BE%E7%BD%AE%E8%8E%B7%E5%8F%96)
            
        *   [3.4.29. 语音助手音量设置](#3429-%E8%AF%AD%E9%9F%B3%E5%8A%A9%E6%89%8B%E9%9F%B3%E9%87%8F%E8%AE%BE%E7%BD%AE)
            
        *   [3.4.30. 语音助手配置设置](#3430-%E8%AF%AD%E9%9F%B3%E5%8A%A9%E6%89%8B%E9%85%8D%E7%BD%AE%E8%AE%BE%E7%BD%AE)
            
        *   [3.4.31. 锁机状态](#3431-%E9%94%81%E6%9C%BA%E7%8A%B6%E6%80%81)
            
        *   [3.4.32. BMS满充校准](#3432-bms%E6%BB%A1%E5%85%85%E6%A0%A1%E5%87%86)
            
        *   [3.4.33. BMS日志记录数量](#3433-bms%E6%97%A5%E5%BF%97%E8%AE%B0%E5%BD%95%E6%95%B0%E9%87%8F)
            
        *   [3.4.34. 获取音频列表](#3434-%E8%8E%B7%E5%8F%96%E9%9F%B3%E9%A2%91%E5%88%97%E8%A1%A8)
            
        *   [3.4.35. 重命名指定音频文件](#3435-%E9%87%8D%E5%91%BD%E5%90%8D%E6%8C%87%E5%AE%9A%E9%9F%B3%E9%A2%91%E6%96%87%E4%BB%B6)
            
        *   [3.4.36. 删除指定音频文件](#3436-%E5%88%A0%E9%99%A4%E6%8C%87%E5%AE%9A%E9%9F%B3%E9%A2%91%E6%96%87%E4%BB%B6)
            
        *   [3.4.37. 查询 添加音频/添加喊话/文字转语音任务状态](#3437-%E6%9F%A5%E8%AF%A2-%E6%B7%BB%E5%8A%A0%E9%9F%B3%E9%A2%91%E6%B7%BB%E5%8A%A0%E5%96%8A%E8%AF%9D%E6%96%87%E5%AD%97%E8%BD%AC%E8%AF%AD%E9%9F%B3%E4%BB%BB%E5%8A%A1%E7%8A%B6%E6%80%81)
            
        *   [3.4.38. 播放指定音频文件](#3438-%E6%92%AD%E6%94%BE%E6%8C%87%E5%AE%9A%E9%9F%B3%E9%A2%91%E6%96%87%E4%BB%B6)
            
        *   [3.4.39. 停止播放音频](#3439-%E5%81%9C%E6%AD%A2%E6%92%AD%E6%94%BE%E9%9F%B3%E9%A2%91)
            
        *   [3.4.40. 修改获取播放属性](#3440-%E4%BF%AE%E6%94%B9%E8%8E%B7%E5%8F%96%E6%92%AD%E6%94%BE%E5%B1%9E%E6%80%A7)
            
        *   [3.4.41. BMS日志最新索引](#3441-bms%E6%97%A5%E5%BF%97%E6%9C%80%E6%96%B0%E7%B4%A2%E5%BC%95)
            
        *   [3.4.42. 获取BMS指定索引日志](#3442-%E8%8E%B7%E5%8F%96bms%E6%8C%87%E5%AE%9A%E7%B4%A2%E5%BC%95%E6%97%A5%E5%BF%97)
            
        *   [3.4.43. APP开启云端图传](#3443-app%E5%BC%80%E5%90%AF%E4%BA%91%E7%AB%AF%E5%9B%BE%E4%BC%A0)
            
        *   [3.4.44. APP云端切换相机](#3444-app%E4%BA%91%E7%AB%AF%E5%88%87%E6%8D%A2%E7%9B%B8%E6%9C%BA)
            
        *   [3.4.45. 获取4G模块配置](#3445-%E8%8E%B7%E5%8F%964g%E6%A8%A1%E5%9D%97%E9%85%8D%E7%BD%AE)
            
        *   [3.4.46. BMS Fg模型有效值](#3446-bms-fg%E6%A8%A1%E5%9E%8B%E6%9C%89%E6%95%88%E5%80%BC)
            
        *   [3.4.47. 设置uwb信令配对设备](#3447-%E8%AE%BE%E7%BD%AEuwb%E4%BF%A1%E4%BB%A4%E9%85%8D%E5%AF%B9%E8%AE%BE%E5%A4%87)
            
        *   [3.4.48. 解除uwb信令配对设备](#3448-%E8%A7%A3%E9%99%A4uwb%E4%BF%A1%E4%BB%A4%E9%85%8D%E5%AF%B9%E8%AE%BE%E5%A4%87)
            
        *   [3.4.49. 定制版本定制需求参数设置和获取](#3449-%E5%AE%9A%E5%88%B6%E7%89%88%E6%9C%AC%E5%AE%9A%E5%88%B6%E9%9C%80%E6%B1%82%E5%8F%82%E6%95%B0%E8%AE%BE%E7%BD%AE%E5%92%8C%E8%8E%B7%E5%8F%96)
            
    *   [3.5. 参数标定（/calibrate）](#35-%E5%8F%82%E6%95%B0%E6%A0%87%E5%AE%9Acalibrate)
        
        *   [3.5.1. 电机/编码器标定](#351-%E7%94%B5%E6%9C%BA%E7%BC%96%E7%A0%81%E5%99%A8%E6%A0%87%E5%AE%9A)
            
        *   [3.5.2. imu校零](#352-imu%E6%A0%A1%E9%9B%B6)
            
    *   [3.6. 通信相关（/interface）](#36-%E9%80%9A%E4%BF%A1%E7%9B%B8%E5%85%B3interface)
        
        *   [3.6.1. 热点名称和密码设置](#361-%E7%83%AD%E7%82%B9%E5%90%8D%E7%A7%B0%E5%92%8C%E5%AF%86%E7%A0%81%E8%AE%BE%E7%BD%AE)
            
    *   [3.7. 默认属性(/properties)](#37-%E9%BB%98%E8%AE%A4%E5%B1%9E%E6%80%A7properties)
        
        *   [3.7.1. 伺服报警内容获取](#371-%E4%BC%BA%E6%9C%8D%E6%8A%A5%E8%AD%A6%E5%86%85%E5%AE%B9%E8%8E%B7%E5%8F%96)
            
        *   [3.7.2. 控制器报警内容获取](#372-%E6%8E%A7%E5%88%B6%E5%99%A8%E6%8A%A5%E8%AD%A6%E5%86%85%E5%AE%B9%E8%8E%B7%E5%8F%96)
            
        *   [3.7.3. 重命名](#373-%E9%87%8D%E5%91%BD%E5%90%8D)
            
        *   [3.7.4. 机型获取](#374-%E6%9C%BA%E5%9E%8B%E8%8E%B7%E5%8F%96) 
            
        *   [3.7.5. 定制版本类型获取](#375-%E5%AE%9A%E5%88%B6%E7%89%88%E6%9C%AC%E7%B1%BB%E5%9E%8B%E8%8E%B7%E5%8F%96) 
            
        *   [3.7.6. 机器人设备序列号](#376-%E6%9C%BA%E5%99%A8%E4%BA%BA%E8%AE%BE%E5%A4%87%E5%BA%8F%E5%88%97%E5%8F%B7)
            
        *   [3.7.7. 国家/地区代码](#377-%E5%9B%BD%E5%AE%B6%E5%9C%B0%E5%8C%BA%E4%BB%A3%E7%A0%81)
            
    *   [3.8. esim卡](#38-esim%E5%8D%A1)
        
        *   [3.8.1. iccid获取](#381-iccid%E8%8E%B7%E5%8F%96)
            
    *   [3.9. 下载（/download）](#39-%E4%B8%8B%E8%BD%BDdownload)
        
        *   [3.9.1. 日志信息](#391-%E6%97%A5%E5%BF%97%E4%BF%A1%E6%81%AF)
            
        *   [3.9.2. 获取狗内部日志的日期列表](#392-%E8%8E%B7%E5%8F%96%E7%8B%97%E5%86%85%E9%83%A8%E6%97%A5%E5%BF%97%E7%9A%84%E6%97%A5%E6%9C%9F%E5%88%97%E8%A1%A8)
            
        *   [3.9.3. 通知机器狗上传日志](#393-%E9%80%9A%E7%9F%A5%E6%9C%BA%E5%99%A8%E7%8B%97%E4%B8%8A%E4%BC%A0%E6%97%A5%E5%BF%97)
            
    *   [3.10. 上传（/upload）](#310-%E4%B8%8A%E4%BC%A0upload)
        
        *   [3.10.1. 局域网音频文件上传](#3101-%E5%B1%80%E5%9F%9F%E7%BD%91%E9%9F%B3%E9%A2%91%E6%96%87%E4%BB%B6%E4%B8%8A%E4%BC%A0)
            
        *   [3.10.2. 4G音频文件上传](#3102-4g%E9%9F%B3%E9%A2%91%E6%96%87%E4%BB%B6%E4%B8%8A%E4%BC%A0)
            
        *   [3.10.3. TTS文字转音频文件](#3103-tts%E6%96%87%E5%AD%97%E8%BD%AC%E9%9F%B3%E9%A2%91%E6%96%87%E4%BB%B6)
            
    *   [3.11. 工程（/project）](#311-%E5%B7%A5%E7%A8%8Bproject)
        
        *   [3.11.1. 程序运行](#3111-%E7%A8%8B%E5%BA%8F%E8%BF%90%E8%A1%8C)
            
        *   [3.11.2. 程序停止](#3112-%E7%A8%8B%E5%BA%8F%E5%81%9C%E6%AD%A2)
            
    *   [3.12. 算法相关(/algs)](#312-%E7%AE%97%E6%B3%95%E7%9B%B8%E5%85%B3algs)
        
        *   [3.12.1. SLAM 新建地图](#3121-slam-%E6%96%B0%E5%BB%BA%E5%9C%B0%E5%9B%BE)
            
        *   [3.12.2. SLAM 获取所有地图列表](#3122-slam-%E8%8E%B7%E5%8F%96%E6%89%80%E6%9C%89%E5%9C%B0%E5%9B%BE%E5%88%97%E8%A1%A8)
            
        *   [3.12.3. SLAM 编辑单个地图（重命名）](#3123-slam-%E7%BC%96%E8%BE%91%E5%8D%95%E4%B8%AA%E5%9C%B0%E5%9B%BE%E9%87%8D%E5%91%BD%E5%90%8D)
            
        *   [3.12.4. SLAM 删除单个地图](#3124-slam-%E5%88%A0%E9%99%A4%E5%8D%95%E4%B8%AA%E5%9C%B0%E5%9B%BE)
            
        *   [3.12.5. SLAM 初始化定位(标点定位)](#3125-slam-%E5%88%9D%E5%A7%8B%E5%8C%96%E5%AE%9A%E4%BD%8D%E6%A0%87%E7%82%B9%E5%AE%9A%E4%BD%8D)
            
        *   [3.12.6. SLAM 开启定位](#3126-slam-%E5%BC%80%E5%90%AF%E5%AE%9A%E4%BD%8D)
            
        *   [3.12.7. SLAM 停止定位](#3127-slam-%E5%81%9C%E6%AD%A2%E5%AE%9A%E4%BD%8D)
            
        *   [3.12.8. SLAM 获取实时定位坐标](#3128-slam-%E8%8E%B7%E5%8F%96%E5%AE%9E%E6%97%B6%E5%AE%9A%E4%BD%8D%E5%9D%90%E6%A0%87)
            
        *   [3.12.9. SLAM 获取建图进度](#3129-slam-%E8%8E%B7%E5%8F%96%E5%BB%BA%E5%9B%BE%E8%BF%9B%E5%BA%A6)
            
        *   [3.12.10. SLAM 获取路网](#31210-slam-%E8%8E%B7%E5%8F%96%E8%B7%AF%E7%BD%91)
            
        *   [3.12.11. SLAM 设置路网](#31211-slam-%E8%AE%BE%E7%BD%AE%E8%B7%AF%E7%BD%91)
            
        *   [3.12.12. SLAM 开始路网导航巡逻](#31212-slam-%E5%BC%80%E5%A7%8B%E8%B7%AF%E7%BD%91%E5%AF%BC%E8%88%AA%E5%B7%A1%E9%80%BB)
            
        *   [3.12.13. SLAM 更新路网导航巡逻状态](#31213-slam-%E6%9B%B4%E6%96%B0%E8%B7%AF%E7%BD%91%E5%AF%BC%E8%88%AA%E5%B7%A1%E9%80%BB%E7%8A%B6%E6%80%81)
            
        *   [3.12.14. SLAM 开始单点导航](#31214-slam-%E5%BC%80%E5%A7%8B%E5%8D%95%E7%82%B9%E5%AF%BC%E8%88%AA)
            
        *   [3.12.15. SLAM 更新单点导航巡逻状态](#31215-slam-%E6%9B%B4%E6%96%B0%E5%8D%95%E7%82%B9%E5%AF%BC%E8%88%AA%E5%B7%A1%E9%80%BB%E7%8A%B6%E6%80%81)
            
        *   [3.12.16. SLAM 获取巡逻状态](#31216-slam-%E8%8E%B7%E5%8F%96%E5%B7%A1%E9%80%BB%E7%8A%B6%E6%80%81)
            
        *   [3.12.17. 获取实时避障状态](#31217-%E8%8E%B7%E5%8F%96%E5%AE%9E%E6%97%B6%E9%81%BF%E9%9A%9C%E7%8A%B6%E6%80%81)
            
        *   [3.12.18. 更新实时避障状态](#31218-%E6%9B%B4%E6%96%B0%E5%AE%9E%E6%97%B6%E9%81%BF%E9%9A%9C%E7%8A%B6%E6%80%81)
            
        *   [3.12.19. 速度模式](#31219-%E9%80%9F%E5%BA%A6%E6%A8%A1%E5%BC%8F)
            
        *   [3.12.20. 速度比例](#31220-%E9%80%9F%E5%BA%A6%E6%AF%94%E4%BE%8B)
            
        *   [3.12.21. 更新视觉选人配置](#31221-%E6%9B%B4%E6%96%B0%E8%A7%86%E8%A7%89%E9%80%89%E4%BA%BA%E9%85%8D%E7%BD%AE)
            
        *   [3.12.22. 获取图传人物选择框信息](#31222-%E8%8E%B7%E5%8F%96%E5%9B%BE%E4%BC%A0%E4%BA%BA%E7%89%A9%E9%80%89%E6%8B%A9%E6%A1%86%E4%BF%A1%E6%81%AF)
            
        *   [3.12.23. 入箱标定](#31223-%E5%85%A5%E7%AE%B1%E6%A0%87%E5%AE%9A)
            

# 1. 修订记录

| **变更说明** | **版本号** | **修改人** | **日期** |
| --- | --- | --- | --- |
| 创建 | v1.0 | 王建民 | 2025-07-28 |
| 完善整合内容 | v1.1 | 蒋皓杰 | 2025-07-31 |
| 单独拉出MH4分支 | v1.2 | 蒋皓杰 | 2025-11-26 |

# 2. 接口设计思想

1.  接口设计需符合RESTful原则
    
2.  对于HTTP接口的POST返回值，如无特殊说明，将统一都包含字段{"status":true/false}。
    
3.  如果接口包含GET，如无特殊说明，则返回的是POST的下发值。
    
4.  接口字段说明：
    
    *   设备连接（/connection）：APP与控制器的连接相关
        
    *   周期协议（/protocol）：用于周期性获取控制器状态
        
    *   参数设置（/settings）：控制器相关的设置
        
    *   参数标定（/calibrate）：机器人标定的相关接口
        
    *   通信相关（/interface）：通信相关接口
        
    *   默认属性(/properties)：控制器的出厂默认属性及相关文件，如上述参数设置的范围、默认值、报警ID的详细定义列表都放在该路径
        
    *   下载（/download）：从控制器中下载文件
        
    *   上传（/upload）：上传文件至控制器
        
    *   工程（/project）：blockly工程相关接口
        
    *   算法相关（/algs）: 算法HTTP服务器相关接口
        
    *   esim(/esim): esim卡信息获取
        

# 3. MH4接口

## 3.1. 接口地址和端口

AP模式固定ip：192.168.1.6

网线直连固定ip：192.168.5.2

嵌入式接口port：22000

算法接口(/algs开头)port: 22002

## 3.2. 设备连接（/connection）

### 3.2.1. 连接

API地址：`http://ip:port/connection/state\`

*   动作：`Post`
    
*   发送：
    

```plaintext
    {
        "currentClient" : 1/2/3/4,
        "clientName" : "xxx",
        "connectionType": "Station" / "AP" / "4G", // 连接方式
    }

```

*   返回：
    

```plaintext
    {
        "status":true/false
    }

```

*   动作：`Get`
    

```plaintext
    {
        "value" : "connected"/"occupied",
        "currentClient" : 1/2/3/4,
        "clientName" : "xxx"
    }

```

*   currentClient 1安卓 ， 2 iOS
    
*   当exchange心跳包停止超过3秒后，控制器就从occupied变为connected状态。当产生exchange心跳包，则从connected变为occupied。
    

### 3.2.2. 连接方式

API地址：`http://ip:port/connection/type\`

*   动作：`Post`
    
*   发送：
    

```plaintext
{
   "value": "Station" / "AP",  // 连接方式
}

```

*   返回：
    

```plaintext
    {
        "status":true/false
    }

```

*   动作：`Get`
    
*   发送：无
    
*   返回：
    

```plaintext
    {
        "value": Station / AP
    }

```

## 3.3. 周期协议（/protocol）

### 3.3.1. exchange

API地址：`http://ip:port/protocol/exchange\`

*   动作：Get
    
*   返回：
    
*   新增字段：prjState、emergencyStop、RTCState
    

```plaintext
    {
        "imu":
        {
            "quaternion":[float, float, float, float],    // 四元数
            "gyroscope":[float, float, float],            // 陀螺仪
            "accelerometer":[float, float, float],        // 加速度计
            "rpy":[float, float, float],                  //【roll，pitch，yaw】
            "temperature":uint8,                          // 温度
        },
        joint: 
        {
            "left_front_leg": 
            {
                "mode":uint8[4],                              // 模式，0-失能，1-报错，2-掉线，3-使能，4-受控，5-回零
                "q":float[4],                                 // 角位置
                "dq":float[4],                                // 角速度
                "ddq":float[4],                               // 角加速度
                "tau_est":float[4],                           // 扭矩
                "q_raw":float[4],                             // 原始角位置
                "dq_raw":float[4],                            // 原始角速度
                "ddq_raw":float[4],                           // 原始角加速度
                "mcu_temp":uint8[4],                          // 伺服控制板温度
                "mos_temp":uint8[4],                          // mos管温度
                "motor_temp":uint8[4],                        // 电机温度
                "bus_voltage":uint8[4],                       // 母线电压
                "is_virtual":bool[4],                         // 是否是虚轴，true-虚轴，false-实轴
                "error_code":uint16_t[[id,id,id],[id],[id],[id]] // 伺服报警码[...4个]
            },
            "right_front_leg": 
            {
                "mode":uint8[4],                              // 模式，0-失能，1-报错，2-掉线，3-使能，4-受控，5-回零
                "q":float[4],                                 // 角位置
                "dq":float[4],                                // 角速度
                "ddq":float[4],                               // 角加速度
                "tau_est":float[4],                           // 扭矩
                "q_raw":float[4],                             // 原始角位置
                "dq_raw":float[4],                            // 原始角速度
                "ddq_raw":float[4],                           // 原始角加速度
                "mcu_temp":uint8[4],                          // 伺服控制板温度
                "mos_temp":uint8[4],                          // mos管温度
                "motor_temp":uint8[4],                        // 电机温度
                "bus_voltage":uint8[4],                       // 母线电压
                "is_virtual":bool[4],                         // 是否是虚轴，true-虚轴，false-实轴
                "error_code":uint16_t[[id,id,id],[id],[id],[id]] // 伺服报警码[...4个]
            },
            "left_rear_leg": 
            {
                "mode":uint8[4],                              // 模式，0-失能，1-报错，2-掉线，3-使能，4-受控，5-回零
                "q":float[4],                                 // 角位置
                "dq":float[4],                                // 角速度
                "ddq":float[4],                               // 角加速度
                "tau_est":float[4],                           // 扭矩
                "q_raw":float[4],                             // 原始角位置
                "dq_raw":float[4],                            // 原始角速度
                "ddq_raw":float[4],                           // 原始角加速度
                "mcu_temp":uint8[4],                          // 伺服控制板温度
                "mos_temp":uint8[4],                          // mos管温度
                "motor_temp":uint8[4],                        // 电机温度
                "bus_voltage":uint8[4],                       // 母线电压
                "is_virtual":bool[4],                         // 是否是虚轴，true-虚轴，false-实轴
                "error_code":uint16_t[[id,id,id],[id],[id],[id]] // 伺服报警码[...4个]
            },
            "right_rear_leg":
            {
                "mode":uint8[4],                              // 模式，0-失能，1-报错，2-掉线，3-使能，4-受控，5-回零
                "q":float[4],                                 // 角位置
                "dq":float[4],                                // 角速度
                "ddq":float[4],                               // 角加速度
                "tau_est":float[4],                           // 扭矩
                "q_raw":float[4],                             // 原始角位置
                "dq_raw":float[4],                            // 原始角速度
                "ddq_raw":float[4],                           // 原始角加速度
                "mcu_temp":uint8[4],                          // 伺服控制板温度
                "mos_temp":uint8[4],                          // mos管温度
                "motor_temp":uint8[4],                        // 电机温度
                "bus_voltage":uint8[4],                       // 母线电压
                "is_virtual":bool[4],                         // 是否是虚轴，true-虚轴，false-实轴
                "error_code":uint16_t[[id,id,id],[id],[id],[id]] // 伺服报警码[...4个]
            }
        },
        "bms":
        {
            "bms_state":uint16,                            // BMS状态
            "afe_state":uint16,                            // AFE芯片状态
            "bms_alarms":uint32,                           // BMS故障码
            "battery_level":uint16,                        // 电池电量百分比
            "battery_health":uint16,                       // 电池健康度
            "pcb_board_temp":uint16,                       // PCB板温度
            "afe_chip_temp":uint16,                        // AFE芯片温度
            "battery_now_current":uint16,                  // 电池包当前电流
            "cells_voltage":uint16[16],                    // 16个电芯电压
            "battery_pack_current_voltage":uint16,         // 电池包电压
            "battery_pack_io_voltage":uint16,              // 电池包放电、充电接口的电压
            "bms_work_time":uint32,                        // BMS运行时间
            "heartbeat":uint16,                            // 心跳
        },
        "error_code": uint32_t[id,id,id,id,id]             // 控制器错误码
        "emergency_stop":bool,                             // 急停
        "prj_state":"running/suspended/stopped",           // 积木程序执行状态suspended为暂停
        "prj_error": string,                               // 积木程序运行报错信息
        "rtc_state":"normal/abnormal",                     // RTC状态
        "current_state": number,                           // 机器狗当前场景状态
        "current_sub_state": number,                       // 机器狗膝盖构型
        "search_light_state": bool,                        // 探照灯打开关闭状态  
        "tracking_info": {
            target_id: number,                             // 机器狗追踪的目标id   
            current_state: number,                         // 机器狗追踪状态 0-追踪关闭； 1-追踪进行中； 2-目标初始寻找中；3-目标重新寻找中；4-进入idle状态 
            type: number                                   // 1 前摄跟随 2 后摄跟随 3 环绕跟随
        },     
        "fourg_enabled": bool,                             // 机器狗4G模块是否已打开
        "current_motion_state": uint8_t,                   // 当前动作状态， // 1-阻尼，2-蹲下, 3-起立
        "obstacle_avoid_available":uint8_t,                // 避障是否可用，0-不可用，1-可用
        "obstacle_avoid_state": bool                       // 避障状态 true-开启，false-关闭
        "log_upload":                                       // 机械狗上传内部日志时的状态变化，当无上传任务时，log_upload为 null
        {
            "status": "packaging",                          // packaging(打包中)/uploading(上传中)
            "progress": 0                                   // 打包中progress固定为0
        },
        "audio":
        {
            "isPlay" : bool,                               // 播放 true / 停止 false
            "type" : uint16,                               // 0-无 1-算法文件 2-算法流 3-app文件 4-app喊话
            "id" : string                                  // 音频id
        },
        "uwb": {
            "uwb_hardware": true,                           // 是否带uwb硬件
            "mcu_attached": true,                           // 是否插上uwb硬件
            "link": true,                                   // 是否配对连接
            "battery_level": 0,                             // 信标电池电量，取值范围0~100的整数（充电中无法读取真实电量会返回255）
            "pair_target": "inffniv1-xxxxxxxx",             // 信令名称
            charging: false                                 // 信令是否正在充电
        }
    }

```

位置单位：弧度，前端转成度展示

温度单位：摄氏度

错误标志：正常和异常

通讯状态：正常和异常

## 3.4. 参数设置（/settings）

### 3.4.1. 版本信息

API地址：`http://ip:port/settings/version\`

*   动作：Get
    
*   返回：
    

```plaintext
    {
        "controller":"XXXXXXX",
        "can":"XXXXX",  //一块can板
        "servo":{
        "left_front_leg":[0.0.0.1,0.0.0.1,0.0.0.1,0.0.0.1],
        "right_front_leg":[0.0.0.1,0.0.0.1,0.0.0.1,0.0.0.1],
        "left_rear_leg":[0.0.0.1,0.0.0.1,0.0.0.1,0.0.0.1],
        "right_rear_leg":[0.0.0.1,0.0.0.1,0.0.0.1,0.0.0.1]
        },
        "system":"XXXXXX",
        "algs": "xxxx",  //PC1算法状态机
        "bms": "xxxx", // bms版本
        "batteryGroupId": "", // 电池组Id
        "audio": "", // 音频板
	    "anc_ble":""  //uwb模块主控芯片
    }

```

参数解释：

*   algs: 算法
    
*   can：can板
    
*   controller：控制器
    
*   servo：伺服 16个全要展示
    
*   system：系统
    

### 3.4.2. 报警清除

*   API地址：`http://ip:port/settings/clearAlarms\`
    
*   动作：`Post`
    
*   发送：无
    
*   返回：
    

```plaintext
    {
        "status":true/false
    }

```

### 3.4.3. 位置超限数据获取设置

/dobot/userdata/user\_project/joints/pos\_limit.json

API地址：`http://ip:port/settings/posLimit\`

*   动作：Post
    
*   发送：
    

```plaintext
数据类型 float
{
  "jointsPosLimit": {
        "left_front_leg": [
            [-12.56637061, 12.56637061],
            [-12.56637061, 12.56637061],
            [-12.56637061, 12.56637061],
            [-12.56637061, 12.56637061]
        ],
        "right_front_leg": [
            [-12.56637061, 12.56637061],
            [-12.56637061, 12.56637061],
            [-12.56637061, 12.56637061],
            [-12.56637061, 12.56637061]
        ],
        "left_rear_leg": [
            [-12.56637061, 12.56637061],
            [-12.56637061, 12.56637061],
            [-12.56637061, 12.56637061],
            [-12.56637061, 12.56637061]
        ],
        "right_rear_leg": [
            [-12.56637061, 12.56637061],
            [-12.56637061, 12.56637061],
            [-12.56637061, 12.56637061],
            [-12.56637061, 12.56637061]
        ]
    }
}


```

*   返回：
    

```plaintext
{
    "status":true/false
}

```

*   动作：Get
    
*   返回：
    

```plaintext
数据类型 float
{
  "jointsPosLimit": {
        "left_front_leg": [
            [-12.56637061, 12.56637061],
            [-12.56637061, 12.56637061],
            [-12.56637061, 12.56637061],
            [-12.56637061, 12.56637061]
        ],
        "right_front_leg": [
            [-12.56637061, 12.56637061],
            [-12.56637061, 12.56637061],
            [-12.56637061, 12.56637061],
            [-12.56637061, 12.56637061]
        ],
        "left_rear_leg": [
            [-12.56637061, 12.56637061],
            [-12.56637061, 12.56637061],
            [-12.56637061, 12.56637061],
            [-12.56637061, 12.56637061]
        ],
        "right_rear_leg": [
            [-12.56637061, 12.56637061],
            [-12.56637061, 12.56637061],
            [-12.56637061, 12.56637061],
            [-12.56637061, 12.56637061]
        ]
    }
}

```

### 3.4.4. 速度超限数据获取设置

/dobot/userdata/user\_project/joints/vel\_limit.json

API地址：`http://ip:port/settings/velLimit\`

*   动作：Post
    
*   发送：
    

```plaintext
数据类型 float
{
  "jointsVelLimit": {
        "left_front_leg": [
            [-34.55751918, 34.55751918],
            [-34.55751918, 34.55751918],
            [-34.55751918, 34.55751918],
            [-34.55751918, 34.55751918]
        ],
        "right_front_leg": [
            [-34.55751918, 34.55751918],
            [-34.55751918, 34.55751918],
            [-34.55751918, 34.55751918],
            [-34.55751918, 34.55751918]
        ],
        "left_rear_leg": [
            [-34.55751918, 34.55751918],
            [-34.55751918, 34.55751918],
            [-34.55751918, 34.55751918],
            [-34.55751918, 34.55751918]
        ],
        "right_rear_leg": [
            [-34.55751918, 34.55751918],
            [-34.55751918, 34.55751918],
            [-34.55751918, 34.55751918],
            [-34.55751918, 34.55751918]
        ]
    }
}


```

*   返回：
    

```plaintext
{
    "status":true/false
}

```

*   动作：Get
    
*   返回：
    

```plaintext
数据类型 float
{
  "jointsVelLimit": {
        "left_front_leg": [
            [-34.55751918, 34.55751918],
            [-34.55751918, 34.55751918],
            [-34.55751918, 34.55751918],
            [-34.55751918, 34.55751918]
        ],
        "right_front_leg": [
            [-34.55751918, 34.55751918],
            [-34.55751918, 34.55751918],
            [-34.55751918, 34.55751918],
            [-34.55751918, 34.55751918]
        ],
        "left_rear_leg": [
            [-34.55751918, 34.55751918],
            [-34.55751918, 34.55751918],
            [-34.55751918, 34.55751918],
            [-34.55751918, 34.55751918]
        ],
        "right_rear_leg": [
            [-34.55751918, 34.55751918],
            [-34.55751918, 34.55751918],
            [-34.55751918, 34.55751918],
            [-34.55751918, 34.55751918]
        ]
    }
}


```

### 3.4.5. 力矩超限数据获取设置

/dobot/userdata/user\_project/joints/tau\_limit.json

API地址：`http://ip:port/settings/torqueLimit\`

*   动作：Post
    
*   发送：
    

```plaintext
数据类型 float
{
  "jointsTorqueLimit": {
        "left_front_leg": [
            [-20, 20],
            [-20, 20],
            [-40, 20],
            [-20, 20]
        ],
        "right_front_leg": [
            [-20, 20],
            [-20, 20],
            [-40, 20],
            [-20, 20]
        ],
        "left_rear_leg": [
            [-20, 20],
            [-20, 20],
            [-40, 20],
            [-20, 20]
        ],
        "right_rear_leg": [
            [-20, 20],
            [-20, 20],
            [-40, 20],
            [-20, 20]
        ]
    }
}

```

*   返回：
    

```plaintext
{
    "status":true/false
}

```

*   动作：Get
    
*   返回：
    

```plaintext
数据类型 float
{
  "jointsTorqueLimit": {
        "left_front_leg": [
            [-20, 20],
            [-20, 20],
            [-40, 20],
            [-20, 20]
        ],
        "right_front_leg": [
            [-20, 20],
            [-20, 20],
            [-40, 20],
            [-20, 20]
        ],
        "left_rear_leg": [
            [-20, 20],
            [-20, 20],
            [-40, 20],
            [-20, 20]
        ],
        "right_rear_leg": [
            [-20, 20],
            [-20, 20],
            [-40, 20],
            [-20, 20]
        ]
    }
}

```

### 3.4.6. KP超限数据获取设置

/dobot/userdata/user\_project/joints/kp\_limit.json

API地址：`http://ip:port/settings/kpLimit\`

*   动作：Post
    
*   发送：
    

```plaintext
数据类型 float
{
    "jointsKpLimit": {
        "left_front_leg": [
            [0, 500],
            [0, 500],
            [0, 500],
            [0, 500]
        ],
        "right_front_leg": [
            [0, 500],
            [0, 500],
            [0, 500],
            [0, 500]
        ],
        "left_rear_leg": [
            [0, 500],
            [0, 500],
            [0, 500],
            [0, 500]
        ],
        "right_rear_leg": [
            [0, 500],
            [0, 500],
            [0, 500],
            [0, 500]
        ]
    }
}

```

*   返回：
    

```plaintext
{
    "status":true/false
}

```

*   动作：Get
    
*   返回：
    

```plaintext
数据类型 float
{
    "jointsKpLimit": {
        "left_front_leg": [
            [0, 500],
            [0, 500],
            [0, 500],
            [0, 500]
        ],
        "right_front_leg": [
            [0, 500],
            [0, 500],
            [0, 500],
            [0, 500]
        ],
        "left_rear_leg": [
            [0, 500],
            [0, 500],
            [0, 500],
            [0, 500]
        ],
        "right_rear_leg": [
            [0, 500],
            [0, 500],
            [0, 500],
            [0, 500]
        ]
    }
}

```

### 3.4.7. KD超限数据获取设置

/dobot/userdata/user\_project/joints/kd\_limit.json

API地址：`http://ip:port/settings/kdLimit\`

*   动作：Post
    
*   发送：
    

```plaintext
数据类型 float
{
    "jointsKdLimit": {
        "left_front_leg": [
            [0, 50],
            [0, 50],
            [0, 50],
            [0, 50]
        ],
        "right_front_leg": [
            [0, 50],
            [0, 50],
            [0, 50],
            [0, 50]
        ],
        "left_rear_leg": [
            [0, 50],
            [0, 50],
            [0, 50],
            [0, 50]
        ],
        "right_rear_leg": [
            [0, 50],
            [0, 50],
            [0, 50],
            [0, 50]
        ]
    }
}

```

*   返回：
    

```plaintext
{
    "status":true/false
}

```

*   动作：Get
    
*   返回：
    

```plaintext
数据类型 float
{
    "jointsKdLimit": {
        "left_front_leg": [
            [0, 50],
            [0, 50],
            [0, 50],
            [0, 50]
        ],
        "right_front_leg": [
            [0, 50],
            [0, 50],
            [0, 50],
            [0, 50]
        ],
        "left_rear_leg": [
            [0, 50],
            [0, 50],
            [0, 50],
            [0, 50]
        ],
        "right_rear_leg": [
            [0, 50],
            [0, 50],
            [0, 50],
            [0, 50]
        ]
    }
}

```

### 3.4.8. 急停

exchange中需要增加状态emergencyStop字段，然后实时去拿状态

API地址：`http://ip:port/settings/emergencyStop\`

*   动作：`Post`
    
*   发送：
    

```plaintext
{
   "value": true / false, // true代表触发软急停
}

```

*   返回：
    

```plaintext
    {
        "status":true/false
    }

```

### 3.4.9. 摇杆控制

API地址：`http://ip:port/settings/movement/joystickControl\`

*   动作：`Post`
    
*   发送：
    

```plaintext
{
	"btn_move": {	// 左摇杆键值
		"x": 0,	// [-32768~32767]
		"y": 0    // [-32768~32767]
	},
	"btn_turn": {	// 右摇杆键值
		"x": 0,	// [-32768~32767]
		"y": 0    // [-32768~32767]
	}

	// 其他按键待定
}

```

*   返回：
    

```plaintext
    {
        "status":true/false
    }

```

### 3.4.10. 获取常用动作和姿势

API地址：`http://ip:port/settings/movement/actions\`

*   动作：`GET`
    
*   发送：无
    
*   返回：
    

```plaintext
    [
        {
            name: 'xxxx',
            id: number,
            type: normal / dangerous  // normal：普通动作 dangerous：危险动作
        },
        {
            name: 'xxxx',
            id: number,
            type: normal / dangerous  // normal：普通动作 dangerous：危险动作
        },
        {
            name: 'xxxx',
            id: number,
            type: normal / dangerous  // normal：普通动作 dangerous：危险动作
        }
        ...
    ]

```

### 3.4.11. 执行常用动作和姿势

API地址：`http://ip:port/settings/movement/action\`

*   动作：`POST`
    
*   发送：
    

```plaintext
{
   id: number
}

```

*   返回：
    

```plaintext
{
  "status": true/false
}

```

### 3.4.12. 动作执行参数

API地址：`http://ip:port/settings/movement/params\`

*   动作：`GET`
    
*   发送：无
    
*   返回：
    

```plaintext
{
    "remainingTimes": number // 高危动作剩余次数
}

```

### 3.4.13. 高危动作协议申请

API地址：`http://ip:port/settings/movement/apply\`

*   动作：`POST`
    
*   发送：
    

```plaintext
{
   snCode: 'xxxx',      // 机器sn码
   uid: 'xxxx',         // 用户账号
   appliedAt: 'xxxx'    // 协议签署时间
}

```

*   返回：
    

```plaintext
{
  "status":true/false
}

```

### 3.4.14. 图传-通知机器狗开启中转服务器（AP模式）和socket连接

APP自身需要监听webrtc协议事件，判断图传是否正常（防止图传出现异常）

exchange接口需要增加图传状态RTCState，支持实时获取HTTP exchange状态。（防止信令服务器异常）

API地址：`http://ip:port/settings/streaming/start\`，

*   动作：`POST`
    
*   发送：无
    
*   返回：
    

```plaintext
{
  "signalUrl": "http:xxxxxxx:xxxx" // AP模式下返回信令服务器地址
  "status":true/false
}

```

### 3.4.15. 图传-停止图传

API地址：`http://ip:port/settings/streaming/stop\`

*   动作：`POST`
    
*   发送：无
    
*   返回：
    

```plaintext
{
  "status":true/false
} 

```

### 3.4.16. 图传-视频录制

API地址：`http://ip:port/settings/streaming/record\`

*   动作：`POST`
    
*   发送：
    

```plaintext
{
   action: start / stop,  // start 代表开始录制，stop代表停止录制
   camera: front / back   // front代表前摄像头，back代表后摄像头
}

```

*   返回：
    

```plaintext
{
  "status":true/false
}

```

### 3.4.17. 图传-录制视频下载

API地址：`http://ip:port/settings/streaming/download\`

*   动作：`GET`
    
*   发送：无
    
*   返回：mp4格式的视频流文件
    

### 3.4.18. 检查更新

API地址：`http://ip:port/settings/ota/checkUpdate\`

*   动作：`GET`
    
*   发送：无
    
*   返回：
    

```plaintext
    {
        "status": true/false,
        "hasUpdate": true/false,     // 是否有新版本
        "totalSize": number,          // 升级包大小（MB）
        "firmwareDesc": "xxxx",       // 固件更新说明（中文）
        "firmwareEnDesc": "xxxx",     // 固件更新说明（英文）
        "version": "x.x.x"            // 有更新时返回目标版本号
    }

```

### 3.4.19. 判断安装包是否已经下载

API地址：`http://ip:port/settings/ota/download\`

*   动作：`Get`
    
*   发送：无
    
*   返回：
    

```plaintext
    {
        "downloadStatus": "downloading" | "downloaded" | "notDownload", // downloading代表下载中，downloaded代表已下载，notDownload代表未下载
        "status":true/false
    }

```

### 3.4.20. 下载OTA升级包

API地址：`http://ip:port/settings/ota/download\`

*   动作：`POST`
    
*   发送：无（下载链接由检查更新接口获取后由控制器内部使用）
    
*   返回：
    

```plaintext
{
  "status":true/false
}

```

### 3.4.21. 通知OTA升级

API地址：`http://ip:port/settings/ota/update\`

*   动作：`POST`
    
*   发送：无
    
*   返回：
    

```plaintext
{
  "status":true/false
}

```

### 3.4.22. OTA包下载进度

API地址：`http://ip:port/settings/ota/downloadProgress\`

*   动作：`GET`
    
*   发送：无
    
*   返回：
    

```plaintext
{
  "status":true/false,
  "progress": number, // 0-100
}

```

### 3.4.23. OTA包校验

API地址：`http://ip:port/settings/ota/verify\`

*   动作：`POST`
    
*   发送：无
    
*   返回：
    

```plaintext
{
  "status":true/false,
  "verified": true/false, // true代表MD5校验通过
  "verifying": true / false // true 代表正在验证，false代表验证完成
}

```

### 3.4.24. OTA包升级进度

API地址：`http://ip:port/settings/ota/updateProgress\`

*   动作：`GET`
    
*   发送：无
    
*   返回：
    

```plaintext
{
  "status":true/false,
  "progress": number, // 0-100
  "log": 'xxxx', // 更新日志
  "failed": true/false, // true代表安装失败
  "updating": true/false // true代表正在升级中
}

```

### 3.4.25. 探照灯开关

exchange中需要增加状态search\_light\_state字段，然后实时去拿状态

API地址：`http://ip:port/settings/searchLight\`

*   动作：`POST`
    
*   发送：
    

```plaintext
{
   "open": true / false, // true 代表打开探照灯
}

```

*   返回：
    

```plaintext
{
  "status":true/false,
}

```

### 3.4.26. 语言设置

API地址：`http://ip:port/settings/language\`

*   动作：`POST`
    
*   发送：
    

```plaintext
{
   "language": "en" / "zh-Hans",  // en: 代表英文，zh-Hans: 中文
}

```

*   返回：
    

```plaintext
{
  "status":true/false,
}

```

### 3.4.27. uid获取及设置

API地址：`http://ip:port/settings/uid\`

*   动作：`GET`
    
*   发送：无
    
*   返回：
    

```plaintext
{
   "uid": "", // APP账号唯一标识
}

```

*   动作：`POST`
    
*   发送：
    

```plaintext
{
   "uid": "", // APP账号唯一标识
}

```

*   返回：
    

```plaintext
{
  "status":true/false
}

```

### 3.4.28. 系统时间设置/获取

API地址：`http://ip:port/settings/systemTime\`

*   动作：`POST`
    
*   发送：
    

```plaintext
{
   "systemTime" : "2020-11-04 16:51:35",  // 系统时间
   "timeZone" : "Asia/Shanghai"           // 时区
}

```

*   返回：
    

```plaintext
{
  "status": true/false
}

```

*   动作：`GET`
    
*   发送：无
    
*   返回：
    

```plaintext
{
   "systemTime" : "2020-11-04 16:51:35",  // 系统时间
   "timeZone" : "Asia/Shanghai"           // 时区
}

```

### 3.4.29. 语音助手音量设置

API地址：`http://ip:port/settings/voice/volume\`

*   动作：`POST`
    
*   发送：
    

```plaintext
{
    "volume": 0-100
}


```

*   返回：
    

```plaintext
{
  "status": true/false
}

```

*   动作：`GET`
    
*   发送：无
    
*   返回：
    

```plaintext
{
    "volume": 0-100
}

```

### 3.4.30. 语音助手配置设置

API地址：`http://ip:port/settings/voice/config\`

*   动作：`POST`
    
*   发送：
    

```plaintext
{
    "switch":true/false,        // 语音唤醒及指令接收开关
    "AITalkSwitch":true/false,  // AI智能语音对话开关
    "role":1/2                  // 对话角色  1--搞怪哈士奇 2--贴心金毛
}

```

*   返回：
    

```plaintext
{
  "status": true/false
}

```

*   动作：`GET`
    
*   发送：无
    
*   返回：
    

```plaintext
{
    "switch":true/false,        // 语音唤醒及指令接收开关
    "AITalkSwitch":true/false,  // AI智能语音对话开关
    "role":1/2                  // 对话角色  1--搞怪哈士奇 2--贴心金毛
}

```

### 3.4.31. 锁机状态

API地址：`http://ip:port/settings/lock\`

*   动作：`GET`
    
*   发送：无
    
*   返回：
    

```plaintext
{
    "locked":true/false,  // 机器是否被锁定，默认false，true-已锁定，false-未锁定
}

```

### 3.4.32. BMS满充校准

API地址：`http://ip:port/settings/bmsCalibration\`

*   动作：`GET`
    
*   发送：无
    
*   返回：
    

```plaintext
{
    "needsCalibration":true/false,  // 是否需要BMS满充校准，默认false，true-需要校准，false-不需要校准
}

```

### 3.4.33. BMS日志记录数量

API地址：`http://ip:port/settings/bmsLogCount\`

*   动作：`GET`
    
*   发送：无
    
*   说明：从BMS 信息中读取日志总记录次数（与周期上报中的 `log_count` 一致）。
    
*   返回：
    

```plaintext
{
    "count": uint16   // 日志总条数
}

```

### 3.4.34. 获取音频列表

API地址：`http://ip:port/settings/voice/list\`

*   动作：`GET`
    
*   发送：无
    
*   返回：
    

```plaintext
{
    "list": [
        {
            "id": "155735354948ohxw",                                                       // id 不可重复
            "type": "audio",                                                                // 类型
            "saveFile": "/userdata/dobot/conf/project/voice/file/save_155735354948ohxw",    // 原始下载文件
            "playFile": "/userdata/dobot/conf/project/voice/file/play_155735354948ohxw",    // 音频播放文件
            "time": "2026-02-10-456",                                                       // 导入时间
            "name": "test1234",                                                             // 名字
            "originType": "mov,mp4,m4a,3gp,3g2,mj2"                                         // 格式
        },
        {
            ****
        }
    ]
}

```

### 3.4.35. 重命名指定音频文件

API地址：`http://ip:port/settings/voice/rename\`

*   动作：`POST`
    
*   发送：
    

```plaintext
{
  "id": "***",
  "name": "新名称"
}

```

*   返回：
    

```plaintext
{
    "status":true/false
}

```

### 3.4.36. 删除指定音频文件

API地址：`http://ip:port/settings/voice/delete\`

*   动作：`POST`
    
*   发送：
    

```plaintext
{
  "id": "***"
}

```

*   返回：
    

```plaintext
{
    "status":true/false
}

```

### 3.4.37. 查询 添加音频/添加喊话/文字转语音任务状态

API地址：`http://ip:port/settings/voice/taskid?taskId=xxxxxx\`

*   动作：`GET`
    
*   发送：无
    
*   返回：
    

| taskStatus | 含义 |
| --- | --- |
| 0 | 已创建 未执行 |
| 1 | 正在执行 |
| 2 | 成功 |
| 3 | 失败 |
| 4 | 被取消（未涉及） |

| taskCode | 含义 |
| --- | --- |
| 0 | 无错误 |
| 1001 | 参数异常 |
| 1002 | 下载失败 |
| 1003 | 文件格式异常 |
| 1004 | 文件转换异常 |
| 1005 | 加载失败 |
| 1006 | 播放失败 |
| 1007 | 数据库写入失败 |
| 1008 | 系统错误 |
| 1009 | TTS超时 |
| 1010 | TTS失败 |
| 1011 | TTS请求异常 |
| 1012 | TTS文件拷贝异常 |

```plaintext
{
    "taskStatus": 0,					// 状态
    "taskCode" : 0,						// 错误码
    "taskResult" : "Task done"			// 结果描述
    "taskError" : "download fail"		// 错误描述
}

```

### 3.4.38. 播放指定音频文件

API地址：`http://ip:port/settings/voice/play\`

*   动作：`POST`
    
*   发送：
    

```plaintext
{
  "id": "***"       // 音频id
}

```

*   返回：
    

```plaintext
{
    "status":true/false
}

```

### 3.4.39. 停止播放音频

API地址：`http://ip:port/settings/voice/stop\`

*   动作：`POST`
    
*   发送：无
    
*   返回：
    

```plaintext
{
    "status":true/false
}

```

### 3.4.40. 修改获取播放属性

API地址：`http://ip:port/settings/voice/property\`

*   动作：`POST`
    
*   发送：
    

```plaintext
{
  "type": 0,            // 0-循环 1-单次 2-多次
  "cycleTime": 1        // 循环次数
}

```

*   返回：
    

```plaintext
{
    "status":true/false
}

```

*   动作：`GET`
    
*   发送：无
    
*   返回：
    

```plaintext
{
  "type": 0,            // 0-循环 1-单次 2-多次
  "cycleTime": 1        // 循环次数
}

```

### 3.4.41. BMS日志最新索引

API地址：`http://ip:port/settings/bmsLogLatestIndex\`

*   动作：`GET`
    
*   发送：无
    
*   说明：从BMS 信息中读取当前日志索引（与周期上报中的 `log_index` 一致）。
    
*   返回：
    

```plaintext
{
    "latestIndex": unit16   // 当前最新日志索引
}

```

### 3.4.42. 获取BMS指定索引日志

API地址：`http://ip:port/settings/bmsLog\`

*   动作：`POST`
    
*   发送：
    

```plaintext
{
    "index": unit16   // 必填，要读取的日志索引；有效范围为 1～latestIndex（latestIndex>0 时）；不满足时返回 400
}

```
```plaintext
{
    "log_index": uint16,                 // 日志索引
    "log_capacity": uint16,              // 日志最大容量
    "log_bms_runtime": uint32,           // BMS 运行时间，单位：1ms
    "log_bms_alarm": uint32,             // BMS 故障码
    "log_bms_status": uint16,            // BMS 状态
    "log_afe_status": uint16,            // AFE 芯片状态
    "log_bms_soc": uint16,               // 电池电量百分比，单位：0.01%
    "log_bms_vtop": uint16,              // 电池包当前电压，单位：0.01V
    "log_bms_vpack": uint16,             // 电池包充放电接口电压，单位：0.01V
    "log_bms_current": int16,          // 电池包当前电流，单位：±0.01A
    "log_bms_vol_ceil": [ uint16 ],     // 16 路电芯电压，单位：0.1mV
    "log_bms_temp_pcb": uint16,          // PCB 温度，单位：0.01°C
    "log_bms_temp_afe": uint16,          // AFE 芯片温度，单位：0.01°C
    "log_bms_temp_ceil": uint16,         // 电芯 NTC 温度，单位：0.01°C
    "log_bms_reserve_flag": uint16,      // 各信号标志位
    "log_bms_rtc_time": uint32,          // BMS RTC Unix 时间戳(由控制器写入)
}

```

### 3.4.43. APP开启云端图传

API地址：`http://ip:port/settings/streaming/agora/start\`

*   动作：`POST`
    
*   发送：
    

```plaintext
{
  "publisherToken": string,
  "publisherId": string,
  "channelName": string,
  "appId": string,
  "expireTime": int,
  "camera": front / back   // front 前摄像头，back 后摄像头
}

```

*   返回：
    

```plaintext
{
  "status": true/false
}

```

### 3.4.44. APP云端切换相机

API地址：`http://ip:port/settings/streaming/switch\`

*   动作：`POST`
    
*   发送：
    

```plaintext
{
  "camera": front / back   // front 前摄像头，back 后摄像头
}

```

*   返回：
    

```plaintext
{
  "status": true/false
}

```

### 3.4.45. 获取4G模块配置

API地址：`http://ip:port/settings/fourgCapacity\`

*   动作：`GET`
    
*   发送：无
    
*   返回：
    

```plaintext
{
  "enable": true/false,  // true: 设备有4G；false: 设备无4G
  "region": 0|1|2|3      // 0=未知或无4G；1=国内(770ASC)；2=欧洲(770ACE)；3=海外(750VA)
}

```

说明：`region` 由 4G 模组 SN判定；`enable=false` 时不查询模组，`region` 固定为 0。

### 3.4.46. BMS Fg模型有效值

API地址：`http://ip:port/settings/bmsFgModelValid\`

*   动作：`GET`
    
*   发送：无
    
*   说明：从 BMS 信息读取 Fg 模型信息有效值；False为无效，True 为有效。
    
*   返回：
    

```plaintext
{
    "fgModelValid": true/false   // Fg模型信息是否有效
}

```

### 3.4.47. 设置uwb信令配对设备

API地址：`http://ip:port/settings/uwbWhitelist\`

*   动作：`Post`
    
*   发送：
    

```plaintext
{
    "name": "inffniv1-xxxxxxxx", // 蓝牙设备名称
}

```

*   返回：
    

```plaintext
{
    "status": true/false
}

```

### 3.4.48. 解除uwb信令配对设备

API地址：`http://ip:port/settings/uwbUnbind\`

*   动作：`Post`
    
*   发送：无
    
*   返回：
    

```plaintext
{
    "status": true/false
}

```

### 3.4.49. 定制版本定制需求参数设置和获取

API地址：`http://ip:port/settings/customParams\`

*   动作：`Get`
    
*   发送：无
    
*   返回：
    

```plaintext
{
    "LvYuan": {
        "welcomeSwitch": true/false   // 绿源主动迎宾功能是否打开，默认关闭
    }
}

```

*   动作：`Post`
    
*   发送：
    

```plaintext
{
    "LvYuan": {
        "welcomeSwitch": true/false   // 绿源主动迎宾功能是否打开
    }
}

```

*   返回：
    

```plaintext
{
    "status": true/false
}

```

## 3.5. 参数标定（/calibrate）

### 3.5.1. 电机/编码器标定

API地址：`http://ip:port/calibrate/joints\`

*   动作：`Post`
    
*   发送：
    

```plaintext
{
	"left_front_leg" : [true,true,true,true],
	"right_front_leg" : [true,true,true,true],
	"left_rear_leg" : [true,true,true,true],
	"right_rear_leg" : [true,true,true,true]
}

```

*   返回：
    

```plaintext
    {
        "status":true/false
    }

```

### 3.5.2. imu校零

API地址：`http://ip:port/calibrate/imu\`

*   动作：`Post`
    
*   发送：无
    
*   返回：
    

```plaintext
    {
        "status":true/false
    }

```

*   返回：
    

```plaintext
    {
        "status":true/false
    }

```

## 3.6. 通信相关（/interface）

### 3.6.1. 热点名称和密码设置

API地址：`http://ip:port/interface/AP\`

*   动作：Post
    
*   发送：
    

```plaintext
{
    "ssid": "ssid_name",  #支持中文和特殊字符，8~32个字符以内
    "passWd":"password"   #仅支持英文和特殊字符，8~64个字符以内
}

```

*   返回
    

```plaintext
{
    "status":true/false
}

```

*   动作：Get
    
*   发送 ：无
    
*   返回：
    

```plaintext
{
    "ssid": "ssid_name",
    "passWd":"password"
}

```

## 3.7. 默认属性(/properties)

### 3.7.1. 伺服报警内容获取

API地址：`http://ip:port/properties/alarmsServo\`

*   动作：GET
    
*   返回：
    

```plaintext
{
  ...
}

```

### 3.7.2. 控制器报警内容获取

API地址：`http://ip:port/properties/alarmsController\`

*   动作：GET
    
*   返回：
    

```plaintext
{
  ...
}

```

### 3.7.3. 重命名

机器人名称和备注

/dobot/userdata/user\_project/properties/device\_profile.json

API地址：`http://ip:port/properties/deviceProfile\`

*   动作：`Post`
    
*   发送：
    

```plaintext
{
   "name": string,  // 名称，默认是机型名字
   "remark": string // 备注
}

```

*   返回：
    

```plaintext
    {
        "status":true/false
    }

```

*   动作：`Get`
    
*   发送： 无
    
*   返回：
    

```plaintext
{
   "name": string,  // 名称，默认是机型名字
   "remark": string // 备注
}

```

### 3.7.4. 机型获取

API地址：`http://ip:port/properties/robotType\`

*   动作：GET
    
*   返回：
    

```plaintext
{
  "robotType":"xxx / unknown (控制器代码获取失败)"
}

```

该文件由cover包生成。机器人类型文件：/dobot/userdata/project/properites/robotType.json

### 3.7.5. 定制版本类型获取

API地址：`http://ip:port/properties/customEdition\`

*   动作：GET
    
*   返回：
    

```plaintext
{
  "customEdition":"Standard | LvYuan",
}

```

Standard: 标准版

LvYuan: 绿源定制版

### 3.7.6. 机器人设备序列号

API地址：`http://ip:port/properties/snCode\`

*   动作：Get
    
*   返回：
    

```plaintext
    {
        "snCode":"XXXXXXX/unknown(控制器代码获取失败)",
    }

```

该文件由批处理工具生成。SN码文件：/dobot/userdata/project/properites/snCode.json

### 3.7.7. 国家/地区代码

API地址：`http://ip:port/properties/countryCode\`

*   动作：`Get`
    
*   发送：无
    
*   返回：
    

```plaintext
{
   "countryCode": "xxxx | unknown"  // xxxx 为有效代码；unknown 表示未获取到或获取失败
}

```

*   动作：`Post`
    
*   发送：
    

```plaintext
{
   "countryCode": string  // 国家/地区代码
}

```

*   返回：
    

```plaintext
    {
        "status": true/false
    }

```

## 3.8. esim卡

### 3.8.1. iccid获取

API地址：`http://ip:port/esim/iccid\`

*   动作：`GET`
    
*   发送：无
    
*   返回：
    

```plaintext
{
   "iccid": "", // esim卡iccid
}

```

## 3.9. 下载（/download）

### 3.9.1. 日志信息

API地址：`http://ip:port/download/logs/all\`

*   动作：GET
    
*   返回：打包成zip,下载所有日志
    

### 3.9.2. 获取狗内部日志的日期列表

API地址：`http://ip:port/download/logs/dates\`

*   动作：GET
    
*   返回：
    

```plaintext
{
  "dates": [
    "2025-02-25T14:30",
    "2025-02-25T14:31",
    "2025-02-25T14:38"
  ]
}

```

### 3.9.3. 通知机器狗上传日志

API地址：`http://ip:port/download/logs/upload\`

*   动作：POST
    
*   请求体：
    

```plaintext
{
  "date": "2025-02-25T14",
  "logserver": "https://dobotex-api-dev.dobot.cc",
  "module": "controller",
  "osVersion": "Android 16",
  "appVersion": "INFFNI-ROVER-App-CN-1.1.0.0-beta2-202604151836",
  "deviceModel": "SM-A245N",
  "userAccount": "158xxxxxxxx"
}

```

*   module 可选：controller | algorithm | all
    
*   返回：
    

```plaintext
{
  "status": true / false,
  "message": "Upload task started / Invalid request: date and module are required"
}

```

说明：机械狗自行调用ossutil上传到云

## 3.10. 上传（/upload）

### 3.10.1. 局域网音频文件上传

API地址：`http://ip:port/upload/formdata/audio\`

*   动作：POST
    
*   发送：
    

| key | value |
| --- | --- |
| name | 文件名 |
| type | audio / shout |
| time | 时间 |
| file | 文件 |

*   返回：
    

```plaintext
{
  "taskId":"**********",        // 随机生成字符串
  "status":true/false
}

```

### 3.10.2. 4G音频文件上传

API地址：`http://ip:port/upload/url/audio\`

*   动作：POST
    
*   发送：
    

```plaintext
{
  "name": "******",                 // app根据实际发送
  "type" : "audio" / "shout",       // audio 文件导入 shout 喊话
  "time" : "******",                // app定义
  "url" : "******"                  // app定义
}

```

*   返回：
    

```plaintext
{
  "taskId" : "*******",             // 随机生成字符串
  "status":true/false
}

```

### 3.10.3. TTS文字转音频文件

API地址：`http://ip:port/upload/tts/audio\`

*   动作：POST
    
*   发送：
    

```plaintext
{
  "name": "******",                     // app根据实际发送
  "type" : "audio" / "shout" / "tts",   // audio 文件导入 shout 喊话 tts文字转语音
  "time" : "******",                    // app定义
  "word" : "******"                     // app定义
}

```

*   返回：
    

```plaintext
{
  "taskId" : "*******",             // 随机生成字符串
  "status":true/false
}

```

## 3.11. 工程（/project）

### 3.11.1. 程序运行

API地址：`http://ip:port/project/run\`

*   动作：`POST`
    
*   发送：
    

```plaintext
{
  pythonCode: string  // Python代码
}

```

*   返回：
    

```plaintext
{
  "status":true/false
}


```

### 3.11.2. 程序停止

API地址：`http://ip:port/project/stop\`

*   动作：`POST`
    
*   发送：无
    
*   返回：
    

```plaintext
{
  "status":true/false
}


```

## 3.12. 算法相关(/algs)

### 3.12.1. SLAM 新建地图

API地址：`http://ip:port/algs/slam/new\`

*   动作：`POST`
    
*   发送：
    

```plaintext
{
    name: string, // 名称
    action: string, // 操作类型：start|stop|cancel， start 启动定位算法（返回地图ID），stop 停止定位算法（完成建图功能），cancel 取消建图（取消建图时要删除图）
}

```

*   返回
    

```plaintext
{
    status:true/false,
}

```

### 3.12.2. SLAM 获取所有地图列表

API地址：`http://ip:port/algs/slam/list\`

*   动作：`GET`
    
*   发送：无
    
*   返回
    

```plaintext
{
    status:true/false,
    data: [
        {
            name: string, // 地图名称
            uri: string, // 地图下载 uri
            status: string, // 建图状态 processing: 建图中； success： 建图成功； fail：建图失败
            createdTime: string，   // 创建时间
        },
         {
            name: string, // 地图名称
            uri: string, // 地图下载 uri
            status: string, // 建图状态 processing: 建图中； success： 建图成功； fail：建图失败
            createdTime: string，   // 创建时间
        }
        ...
    ]
}

```

### 3.12.3. SLAM 编辑单个地图（重命名）

API地址：`http://ip:port/algs/slam/edit\`

*   动作：`POST`
    
*   发送：
    

```plaintext
{
    oldName: string, // 旧的名称
    newName: string, // 新的名称
}

```

*   返回
    

```plaintext
{
    "status":true/false,
}

```

### 3.12.4. SLAM 删除单个地图

API地址：`http://ip:port/algs/slam/delete\`

*   动作：`POST`
    
*   发送：
    

```plaintext
{
    name: string, // 地图名称
}

```

*   返回
    

```plaintext
{
    status: true/false,
}

```

### 3.12.5. SLAM 初始化定位(标点定位)

API地址：`http://ip:port/algs/slam/initPosition\`

*   动作：`POST`
    
*   发送：
    

```plaintext
{
    "name": string,   // 地图名称
    "x": number,    // x坐标
    "y": number,    // y坐标
    "z": number,    // z坐标（二维地图可不传）
    "rad": number,  // 旋转角度
    "type": string, // 'map' - 地图坐标系、'image' - 图像坐标系
}

```

*   返回：
    

```plaintext
{
    "status": true/false,
}

```

### 3.12.6. SLAM 开启定位

API地址：`http://ip:port/algs/slam/startPosition\`

*   动作：`POST`
    
*   发送：
    

```plaintext
{
    "name": string,   // 地图名称
}

```

*   返回：
    

```plaintext
{
    "status": true/false,
}

```

### 3.12.7. SLAM 停止定位

API地址：`http://ip:port/algs/slam/stopPosition\`

*   动作：`POST`
    
*   发送：
    

```plaintext
{
    "name": string,   // 地图名称
}

```

*   返回：
    

```plaintext
{
    "status": true/false,
}

```

### 3.12.8. SLAM 获取实时定位坐标

API地址：`http://ip:port/algs/slam/postion\`

*   动作：`POST`
    
*   发送：
    

```plaintext
{
    "name": string,   // 地图名称
}

```

*   返回：
    

```plaintext
{
    "status": true/false,
    "data": {
        status: number, // 定位状态
        position: {// 坐标
            x: float, // x 坐标
            y: float, // y 坐标
            rad: float, // 旋转角度
            type: string, //'map' - 地图坐标系、'image' - 图像坐标系
        }
    }
}

```

### 3.12.9. SLAM 获取建图进度

API地址：`http://ip:port/algs/slam/queryProgressing\`

*   动作：`POST`
    
*   发送：
    

```plaintext
[name1, name2, name3]

```

*   返回：
    

```plaintext
{
    "status": true/false,
    "data": [{
        name: string, // 名称
        status: string, // processing | success | fail
        progress: number, //  进度（百分比的数字）
    }]
}

```

### 3.12.10. SLAM 获取路网

API地址：`http://ip:port/algs/slam/roadNetwork?name=mapName\`

*   动作：`GET`
    
*   发送：
    

```plaintext
[name1, name2, name3]

```

*   返回：
    

```plaintext
{
  "status": boolean,
  "data": [
    {
      "id": integer,
      "name": string,
      "next": integer,
      "pose": {
        "x": float,
        "y": float,
        "z": float,
        "rad": float,
        "type": string, // "image" | "map"
      }
    }
  ]
}

```

### 3.12.11. SLAM 设置路网

API地址：`http://ip:port/algs/slam/roadNetwork\`

*   动作：`POST`
    
*   发送：
    

```plaintext
{
  "name": string,  // 地图名称
  "roadNetworkPoints": [
    {
      "id": integer,
      "name": string,
      "next": integer,
      "pose": {
        "x": float,
        "y": float,
        "z": float,
        "rad": float,
        "type": string, // "image" | "map"
      }
    }
  ]
}

```

*   返回：
    

```plaintext
{
  "status": true/false,
}

```

### 3.12.12. SLAM 开始路网导航巡逻

API地址：`http://ip:port/algs/slam/startNetworkPatrol\`

*   动作：`POST`
    
*   发送：
    

```plaintext
{
    "name": string, // 地图名称
    "roadNetworkPoints": [ // 巡逻标记点ID
        1, // integer 标记点ID 
        2
    ],
    "repeatCount": 1 // 巡逻次数
}

```

*   返回：
    

```plaintext
{
  "status": true/false,
}

```

### 3.12.13. SLAM 更新路网导航巡逻状态

API地址：`http://ip:port/algs/slam/updateNetworkPatrolStatus\`

*   动作：`POST`
    
*   发送：
    

```plaintext
{
    "name": string, // 地图名称
    "status": string // pause-暂停，patrolling-巡逻中，cancel-取消
}

```

*   返回：
    

```plaintext
{
  "status": true/false,
}

```

### 3.12.14. SLAM 开始单点导航

API地址：`http://ip:port/algs/slam/startSinglePointPatrol\`

*   动作：`POST`
    
*   发送：
    

```plaintext
{
    "name": string, // 地图名称
    "position": { // 目标点
        "x": float,
        "y": float,
        "z": float,
        "rad": float,
        "type": string // "image" | "map"
    }
}

```

*   返回：
    

```plaintext
{
  "status": true/false,
}

```

### 3.12.15. SLAM 更新单点导航巡逻状态

API地址：`http://ip:port/algs/slam/updateSinglePointPatrolStatus\`

*   动作：`POST`
    
*   发送：
    

```plaintext
{
    "name": string, // 地图名称
    "status": string // pause-暂停，patrolling-巡逻中，cancel-取消
}

```

*   返回：
    

```plaintext
{
  "status": true/false,
}

```

### 3.12.16. SLAM 获取巡逻状态

API地址：`http://ip:port/algs/slam/patrolStatus\`

*   动作：`GET`
    
*   发送：
    

无

*   返回：
    

```plaintext
{
    "status": boolean,
    "data": {
        "status": string, // patrolling-巡逻中，pause-暂停，finish-完成，cancel-取消 
        "type": string, // single-单点导航巡逻，roadNetwork-路网导航巡逻
        "name": string // 地图名称
    }
}

```

### 3.12.17. 获取实时避障状态

API地址：`http://ip:port/algs/settings/movement/obstacleAvoidance\`

*   动作：`GET`
    
*   发送：无
    
*   返回：
    

```plaintext
{
    "open": true/false, // 是否开启避障
}

```

### 3.12.18. 更新实时避障状态

API地址：`http://ip:port/algs/settings/movement/obstacleAvoidance\`

*   动作：`POST`
    
*   发送：
    

```plaintext
{
    "open": true/false, // 是否开启避障
}

```

*   返回：
    

```plaintext
{
     "status": true/false
}

```

### 3.12.19. 速度模式

API地址：`http://ip:port/algs/settings/movement/speedMode\`

*   动作：`POST`
    
*   发送：
    

```plaintext
{
    "mode": 'low' / 'high'  // high代表高速模式
}


```

*   返回：
    

```plaintext
{
  "status": true/false
}

```

*   动作：`GET`
    
*   发送：无
    
*   返回：
    

```plaintext
{
    "mode": 'low' / 'high'  // high代表高速模式
}

```

### 3.12.20. 速度比例

API地址：`http://ip:port/algs/settings/movement/speedRatio\`

*   动作：`POST`
    
*   发送：
    

```plaintext
{
    "ratio": number   // 10 - 100 
}


```

*   返回：
    

```plaintext
{
  "status": true/false
}

```

*   动作：`GET`
    
*   发送：无
    
*   返回：
    

```plaintext
{
    "ratio": number   // 10 - 100 如果没设置过，默认返回50
}

```

### 3.12.21. 更新视觉选人配置

API地址：`http://ip:port/algs/settings/autoIntelligence/follow\`

*   动作：`POST`
    
*   发送：
    

```plaintext
{
    "open": 0 | 1 | 2, // 0：关闭；1：开启；2：预跟随
    "type": "rear" | "front", // 跟随方式，rear：后跟随；front：前跟随
    "distance": 1.5 | 3.0, // 跟随距离，1.5m或3.0m
    "target_id": int, // 目标ID
    "target_x": double, // 目标x坐标
    "target_y": double, // 目标y坐标
}

```

*   返回：
    

```plaintext
{
    "status": true/false,
}

```

### 3.12.22. 获取图传人物选择框信息

API地址：`http://ip:port/algs/settings/autoIntelligence/follow/getViewPersonInfo\`

*   动作：`GET`
    
*   发送： 无
    
*   返回：
    

```plaintext
{
    "data": [
        {
            "id": int, // 人物ID
            "x": double, // 人物x坐标
            "y": double, // 人物y坐标
            "width": double, // 人物宽度
            "height": double, // 人物高度
        }
        ...
    ]   
}

```

### 3.12.23. 入箱标定

API地址：`http://ip:port/algs/calibrate/box\`

*   动作：`POST`
    
*   发送： 无
    
*   返回：
    

```plaintext
{
    "status": true/false,
}

```