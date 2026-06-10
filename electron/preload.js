const { contextBridge, ipcRenderer } = require('electron')

contextBridge.exposeInMainWorld('electronAPI', {
  platform: process.platform,
  version:  process.versions.electron,

  // Window controls — called from React header
  hideWindow: () => ipcRenderer.send('hide-window'),
  quitApp:    () => ipcRenderer.send('quit-app'),

  // Config — vault path, api port etc.
  getConfig: () => ipcRenderer.invoke('get-config'),
})
