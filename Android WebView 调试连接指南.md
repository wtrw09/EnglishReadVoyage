# Android WebView 调试连接指南

## 条件准备

1. **adb 配置**：`D:\ProgramSpecial\androidSDK\platform-tools` 加入系统 PATH
2. **AVD 运行**：模拟器中 App 在前台运行
3. **App 需为 debug 构建**（`npx cap run android` 默认就是）

## 构建并运行 App

```powershell
# frontend 目录下
npx vite build              # 构建前端
npx cap copy android        # 同步到 Android 项目
npx cap run android         # 在 AVD 上运行
```

修改代码后快速更新（不需重新运行）：

```powershell
npm run android:sync
# 然后在 AVD 中手动重启/刷新 App
```

## 方法一：Edge 浏览器（推荐，国内最稳定）

1. 打开 `edge://inspect`
2. 勾选 **"Discover USB devices"**
3. 在 `#EMULATOR-5554` 下找到 `WebView in com.englishreadvoyage.app`
4. 点击 **"inspect"** 打开 DevTools

## 方法二：手动端口转发（边录边用）

```powershell
# 1. 每次新终端先配置 adb
$env:Path += ";D:\ProgramSpecial\androidSDK\platform-tools"

# 2. 查找 App 进程 PID
adb shell pidof com.englishreadvoyage.app
# 输出示例：4184

# 3. 转发 WebView 调试端口（PID 每次运行可能不同）
adb forward tcp:9222 localabstract:webview_devtools_remote_<PID>

# 4. 浏览器打开 edge://inspect
# 在 Remote Target → #LOCALHOST → localhost:9222 下找到页面
# 点击 "inspect" 打开 DevTools
```

## 在 DevTools 中调试

### Console 面板

- 切换到 **Console**（控制台）标签
- 设置日志级别为 **"Verbose"**（默认只显示 Info 以上）
- 操作 App，观察诊断日志输出

### 关键诊断日志

| 日志前缀 | 说明 |
|----------|------|
| `[App] 横幅渲染条件` | 横幅是否显示及原因 |
| `[App] 点击 tokenExpired` | 用户点击过期横幅 |
| `[Login] onMounted` | 进入登录页时的状态 |
| `[Login] checkServerHealth` | 服务端连接检查 |
| `[NetworkStatus] 服务器可达但无 token` | 无 token 时状态切换 |
| `[Login] 登录成功` | 登录后的 Pinia/路由状态 |
| `[Login] nextTick 后` | 导航前的最终状态 |

## 注意事项

- **PID 变化**：每次重启 App 进程 ID 会变，需重新执行 `adb forward`
- **新终端**：新开 PowerShell 需重新加 PATH，或永久加到系统环境变量
- **Chrome 问题**：`chrome://inspect` 的 DevTools 前端在国内访问不稳定，推荐用 Edge
- **日志级别**：一定要在 Console 面板设置 Verbose 级别，否则 console.log 不显示
