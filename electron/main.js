'use strict'

const {
  app,
  BrowserWindow,
  Tray,
  Menu,
  globalShortcut,
  ipcMain,
  screen,
  nativeImage,
  shell,
} = require('electron')
const path  = require('path')
const { spawn, execSync } = require('child_process')

const isDev    = process.env.NODE_ENV === 'development'
const VITE_URL = 'http://localhost:5173'

// ---------------------------------------------------------------------------
// State
// ---------------------------------------------------------------------------
let tray         = null
let win          = null
let pythonProc   = null
let isQuitting   = false

// ---------------------------------------------------------------------------
// Python backend lifecycle
// ---------------------------------------------------------------------------

function startPythonBackend() {
  // In dev: expect user already ran uvicorn via dev.bat
  // In production: spawn bundled python
  if (isDev) return

  const pythonExe  = path.join(process.resourcesPath, 'backend', 'python.exe')
  const scriptPath = path.join(process.resourcesPath, 'backend', 'run.py')

  pythonProc = spawn(pythonExe, [scriptPath], {
    detached: false,
    stdio:    'ignore',
    windowsHide: true,
  })

  pythonProc.on('error', (err) => {
    console.error('[backend] Failed to start Python:', err.message)
  })
}

function stopPythonBackend() {
  if (!pythonProc) return
  try {
    // Windows: kill the whole process tree
    execSync(`taskkill /PID ${pythonProc.pid} /T /F`, { stdio: 'ignore' })
  } catch (_) {
    pythonProc.kill()
  }
  pythonProc = null
}

// ---------------------------------------------------------------------------
// Tray icon
// ---------------------------------------------------------------------------

function getIconPath() {
  // Use PNG for tray (works on all platforms), ICO for taskbar
  const name = process.platform === 'win32' ? 'tray-icon.ico' : 'tray-icon.png'
  return path.join(__dirname, 'assets', name)
}

function createTray() {
  const iconPath = getIconPath()
  let icon

  try {
    icon = nativeImage.createFromPath(iconPath)
    // Resize to 16x16 for tray — Windows expects small icons
    icon = icon.resize({ width: 16, height: 16 })
  } catch (_) {
    icon = nativeImage.createEmpty()
  }

  tray = new Tray(icon)
  tray.setToolTip('Obsidian Agent')

  const contextMenu = Menu.buildFromTemplate([
    {
      label: 'Open',
      click: () => toggleWindow(),
    },
    { type: 'separator' },
    {
      label: 'Open Vault Folder',
      click: () => {
        // Read vault path from env/config — fall back gracefully
        const vaultPath = process.env.VAULT_PATH || ''
        if (vaultPath) shell.openPath(vaultPath)
      },
    },
    { type: 'separator' },
    {
      label: 'Start with Windows',
      type: 'checkbox',
      checked: isAutoLaunchEnabled(),
      click: (item) => setAutoLaunch(item.checked),
    },
    { type: 'separator' },
    {
      label: 'Quit',
      click: () => {
        isQuitting = true
        app.quit()
      },
    },
  ])

  tray.setContextMenu(contextMenu)
  tray.on('click', () => toggleWindow())
}

// ---------------------------------------------------------------------------
// Auto-launch (Windows startup)
// ---------------------------------------------------------------------------

function isAutoLaunchEnabled() {
  if (isDev) return false
  try {
    const loginItems = app.getLoginItemSettings()
    return loginItems.openAtLogin
  } catch (_) {
    return false
  }
}

function setAutoLaunch(enable) {
  if (isDev) return
  app.setLoginItemSettings({
    openAtLogin: enable,
    path:        app.getPath('exe'),
    name:        'Obsidian Agent',
  })
}

// ---------------------------------------------------------------------------
// Floating window
// ---------------------------------------------------------------------------

function createWindow() {
  const display     = screen.getPrimaryDisplay()
  const { width: sw, height: sh } = display.workAreaSize
  const winWidth    = 380
  const winHeight   = 640
  const margin      = 12

  win = new BrowserWindow({
    width:  winWidth,
    height: winHeight,
    // Anchored bottom-right just above tray area
    x: sw - winWidth  - margin,
    y: sh - winHeight - margin,

    // Frameless floating popup
    frame:           false,
    resizable:       true,
    skipTaskbar:     true,       // don't show in taskbar
    alwaysOnTop:     false,
    transparent:     false,
    backgroundColor: '#0d1117',
    hasShadow:       true,

    webPreferences: {
      preload:          path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration:  false,
      sandbox:          true,
    },

    show: false,  // start hidden — shown on first tray click
  })

  // Load UI
  if (isDev) {
    win.loadURL(VITE_URL)
  } else {
    win.loadFile(path.join(__dirname, 'renderer-dist', 'index.html'))
  }

  // Auto-hide when focus leaves the window
  win.on('blur', () => {
    // Small delay so clicks on tray icon don't double-toggle
    setTimeout(() => {
      if (win && !win.isDestroyed() && win.isVisible()) {
        win.hide()
      }
    }, 150)
  })

  // Prevent full close — just hide
  win.on('close', (e) => {
    if (!isQuitting) {
      e.preventDefault()
      win.hide()
    }
  })
}

// ---------------------------------------------------------------------------
// Toggle window visibility anchored above tray icon
// ---------------------------------------------------------------------------

function toggleWindow() {
  if (!win) return

  if (win.isVisible()) {
    win.hide()
    return
  }

  positionWindow()
  win.show()
  win.focus()
}

function positionWindow() {
  if (!win || !tray) return

  const trayBounds  = tray.getBounds()
  const winBounds   = win.getBounds()
  const display     = screen.getDisplayNearestPoint({ x: trayBounds.x, y: trayBounds.y })
  const workArea    = display.workArea
  const margin      = 8

  // Centre above the tray icon, push up from bottom
  let x = Math.round(trayBounds.x + trayBounds.width  / 2 - winBounds.width  / 2)
  let y = workArea.y + workArea.height - winBounds.height - margin

  // Guard against going off-screen on the left or right
  x = Math.max(workArea.x + margin, Math.min(x, workArea.x + workArea.width - winBounds.width - margin))

  win.setPosition(x, y, false)
}

// ---------------------------------------------------------------------------
// IPC handlers (called from renderer via preload bridge)
// ---------------------------------------------------------------------------

ipcMain.on('hide-window',   () => win && win.hide())
ipcMain.on('quit-app',      () => { isQuitting = true; app.quit() })
ipcMain.handle('get-config', () => ({
  vaultPath:  process.env.VAULT_PATH  || '',
  apiPort:    process.env.API_PORT    || '8000',
  isDev,
}))

// ---------------------------------------------------------------------------
// App lifecycle
// ---------------------------------------------------------------------------

// Single instance lock — prevent multiple tray icons
if (!app.requestSingleInstanceLock()) {
  app.quit()
} else {
  app.on('second-instance', () => {
    // Someone tried to launch a second instance — show our window
    if (win) toggleWindow()
  })
}

app.whenReady().then(() => {
  // Hide from macOS dock / Windows taskbar
  if (app.dock) app.dock.hide()

  startPythonBackend()
  createWindow()
  createTray()
  registerGlobalShortcut()
})

app.on('before-quit', () => {
  isQuitting = true
  globalShortcut.unregisterAll()
  stopPythonBackend()
})

app.on('window-all-closed', () => {
  // Do nothing — we want the app to stay in tray
})

// ---------------------------------------------------------------------------
// Global hotkey
// ---------------------------------------------------------------------------

function registerGlobalShortcut() {
  const registered = globalShortcut.register('CommandOrControl+Shift+Space', () => {
    toggleWindow()
  })
  if (!registered) {
    console.warn('[hotkey] Ctrl+Shift+Space could not be registered (already in use?)')
  }
}

