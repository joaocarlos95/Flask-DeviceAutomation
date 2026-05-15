(function(window, document, $) {
    'use strict';

    var App = {
        sidebarKey: 'panda.sidebar.expanded',
        targetSourceKey: 'panda.target.source',

        init: function() {
            this.cache();
            this.applySidebarState();
            this.applyTargetSource();
            this.bindSidebar();
            this.bindTargetSource();
            this.bindFolderBrowser();
            this.bindSettings();
            this.bindSections();
            this.bindPanels();
        },

        cache: function() {
            this.sidebarToggle = document.querySelector('.sidebar-toggle');
            this.sourceButtons = document.querySelectorAll('.target-source-button');
            this.inventoryInput = document.getElementById('inventoryRootDirectory');
            this.browserButton = document.getElementById('openInventoryBrowser');
            this.browser = document.getElementById('inventoryFolderBrowser');
            this.browserPath = document.getElementById('folderBrowserPath');
            this.browserList = document.getElementById('folderBrowserList');
            this.browserStatus = document.getElementById('folderBrowserStatus');
            this.netboxStatus = document.getElementById('netboxConnectionStatus');
            this.browserUp = document.getElementById('folderBrowserUp');
            this.settingsMessage = document.getElementById('targetSettingsMessage');
            this.settingsSaveButton = document.getElementById('targetSettingsSave');
            this.netboxUrlInput = document.getElementById('netboxUrl');
            this.netboxTokenInput = document.getElementById('netboxToken');
            this.toastHost = document.getElementById('appToastHost');
            if (!this.toastHost) {
                this.toastHost = document.createElement('div');
                this.toastHost.id = 'appToastHost';
                this.toastHost.className = 'app-toast-host';
                document.body.appendChild(this.toastHost);
            }
        },

        applySidebarState: function() {
            this.setSidebar(sessionStorage.getItem(this.sidebarKey) === 'true');
        },

        setSidebar: function(expanded) {
            document.documentElement.classList.toggle('sidebar-expanded', expanded);
            document.documentElement.classList.toggle('sidebar-collapsed', !expanded);
            sessionStorage.setItem(this.sidebarKey, expanded ? 'true' : 'false');
        },

        bindSidebar: function() {
            var self = this;

            if (!this.sidebarToggle) {
                return;
            }

            this.sidebarToggle.addEventListener('click', function() {
                self.setSidebar(!document.documentElement.classList.contains('sidebar-expanded'));
            });
        },

        applyTargetSource: function() {
            this.updateTargetSourceButtons(sessionStorage.getItem(this.targetSourceKey) || 'inventory');
        },

        setTargetSource: function(source) {
            sessionStorage.setItem(this.targetSourceKey, source);
            this.updateTargetSourceButtons(source);

            window.dispatchEvent(new CustomEvent('panda:target-source-change', {detail: {source: source}}));
        },

        updateTargetSourceButtons: function(source) {
            var nextSource = source === 'inventory' ? 'netbox' : 'inventory';
            var currentLabel = source === 'inventory' ? 'Inventory' : 'NetBox';

            this.sourceButtons.forEach(function(button) {
                button.classList.toggle('active', button.dataset.targetSource === source);

                if (button.classList.contains('source-switch')) {
                    button.dataset.targetSource = nextSource;
                    button.classList.toggle('is-netbox', source === 'netbox');
                    button.title = nextSource === 'inventory' ? 'Switch to inventory' : 'Switch to NetBox';
                }
            });

            document.querySelectorAll('[data-source-current]').forEach(function(label) {
                label.textContent = currentLabel;
            });

            document.querySelectorAll('[data-source-switch-folder]').forEach(function(icon) {
                icon.hidden = source === 'netbox';
            });

            document.querySelectorAll('[data-source-switch-netbox]').forEach(function(icon) {
                icon.hidden = source !== 'netbox';
            });
        },

        bindTargetSource: function() {
            var self = this;

            this.sourceButtons.forEach(function(button) {
                button.addEventListener('click', function() {
                    self.setTargetSource(button.dataset.targetSource);
                });
            });
        },

        bindFolderBrowser: function() {
            var self = this;

            if (this.browserButton && this.inventoryInput) {
                this.browserButton.addEventListener('click', function() {
                    if (self.browser && !self.browser.hidden) {
                        self.browser.hidden = true;
                        return;
                    }
                    self.loadFolder(self.inventoryInput.value, true);
                });
            }

            if (this.browserUp) {
                this.browserUp.addEventListener('click', function() {
                    if (self.browserUp.dataset.path) {
                        self.loadFolder(self.browserUp.dataset.path, true);
                    }
                });
            }

            $('#sourceSettingsModal').on('shown.bs.modal', function() {
                if (self.inventoryInput) {
                    self.loadFolder(self.inventoryInput.value, false);
                }
                self.refreshNetboxStatus();
            });

        },

        loadFolder: function(path, showBrowser) {
            var self = this;
            var shouldShowBrowser = showBrowser !== false;

            $.ajax({
                url: '/browse_folders',
                data: {path: path},
                success: function(data) {
                    self.renderFolders(data, shouldShowBrowser);
                },
                error: function() {
                    self.showSettingsMessage('Could not open that folder.');
                }
            });
        },

        renderFolders: function(data, showBrowser) {
            var self = this;
            var shouldShowBrowser = showBrowser !== false;

            if (!this.browser || !this.browserList || !this.browserPath || !this.browserUp || !this.browserStatus) {
                return;
            }

            this.browser.hidden = !shouldShowBrowser;
            this.browserPath.textContent = data.currentPath;
            this.browserUp.disabled = !data.parentPath;
            this.browserUp.dataset.path = data.parentPath || '';
            if (this.inventoryInput) {
                this.inventoryInput.value = data.currentPath;
            }
            this.browserStatus.className = 'folder-browser-status ' + (data.hasInventoryFiles ? 'valid' : 'invalid');
            this.browserStatus.textContent = data.hasInventoryFiles
                ? 'Inventory files found.'
                : 'Inventory files missing.';
            this.browserList.innerHTML = '';

            if (!data.folders.length) {
                this.browserList.appendChild(this.createMessage('No subfolders found.'));
            }

            data.folders.forEach(function(folder) {
                self.browserList.appendChild(self.createFolderButton(folder));
            });
        },

        createFolderButton: function(folder) {
            var self = this;
            var button = document.createElement('button');
            var name = document.createElement('span');
            var icon = document.createElement('i');
            var label = document.createElement('span');

            button.type = 'button';
            button.className = 'folder-option';
            name.className = 'folder-option-name';
            icon.className = 'fas fa-folder';
            icon.setAttribute('aria-hidden', 'true');
            label.textContent = folder.name;
            name.appendChild(icon);
            name.appendChild(label);
            button.appendChild(name);

            if (folder.hasInventoryFiles) {
                var badge = document.createElement('span');
                badge.className = 'folder-option-badge';
                badge.textContent = 'inventory';
                button.appendChild(badge);
            }

            button.addEventListener('click', function() {
                self.loadFolder(folder.path);
            });

            return button;
        },

        createMessage: function(text) {
            var message = document.createElement('div');
            message.className = 'settings-message visible';
            message.textContent = text;
            return message;
        },

        refreshNetboxStatus: function() {
            var self = this;

            if (!this.netboxStatus) {
                return;
            }

            $.ajax({
                url: '/netbox_status',
                success: function(data) {
                    var connected = !!(data && data.connected);
                    self.netboxStatus.className = 'folder-browser-status ' + (connected ? 'valid' : 'invalid');
                    self.netboxStatus.textContent = connected ? 'Connected' : (data && data.message ? data.message : 'Not connected');
                },
                error: function() {
                    self.netboxStatus.className = 'folder-browser-status invalid';
                    self.netboxStatus.textContent = 'Not connected';
                }
            });
        },

        bindSettings: function() {
            var self = this;
            if (this.settingsSaveButton) {
                this.settingsSaveButton.addEventListener('click', function() {
                    self.saveSettingsNow();
                });
            }
        },

        saveSettingsNow: function() {
            var self = this;
            $.ajax({
                url: '/target_settings',
                type: 'POST',
                contentType: 'application/json',
                data: JSON.stringify({
                    inventoryDirectory: self.inventoryInput ? self.inventoryInput.value : '',
                    netboxUrl: self.netboxUrlInput ? self.netboxUrlInput.value : '',
                    netboxToken: self.netboxTokenInput ? self.netboxTokenInput.value : ''
                }),
                success: function() {
                    self.showSettingsMessage('');
                    self.showToast('Settings saved', 'success');
                    self.refreshNetboxStatus();
                },
                error: function() {
                    self.showSettingsMessage('Could not save');
                    self.showToast('Could not save settings', 'error');
                }
            });
        },

        showSettingsMessage: function(text) {
            if (!this.settingsMessage) {
                return;
            }

            this.settingsMessage.textContent = text || '';
            if (text) {
                this.settingsMessage.classList.add('visible');
            } else {
                this.settingsMessage.classList.remove('visible');
            }
        },

        showToast: function(text, type) {
            if (!this.toastHost) {
                return;
            }

            var toast = document.createElement('div');
            var icon = document.createElement('i');
            var body = document.createElement('span');
            var toastType = type || 'info';

            toast.className = 'app-toast ' + toastType;
            icon.className = toastType === 'success' ? 'fas fa-check-circle' : (toastType === 'error' ? 'fas fa-circle-exclamation' : 'fas fa-info-circle');
            icon.setAttribute('aria-hidden', 'true');
            body.textContent = text;
            toast.appendChild(icon);
            toast.appendChild(body);
            this.toastHost.appendChild(toast);

            setTimeout(function() {
                toast.remove();
            }, 2600);
        },

        bindSections: function() {
            document.querySelectorAll('[data-toggle-section]').forEach(function(button) {
                button.addEventListener('click', function() {
                    button.closest('.choice-section').classList.toggle('collapsed');
                });
            });
        },

        bindPanels: function() {
            document.querySelectorAll('[data-toggle-panel]').forEach(function(header) {
                header.addEventListener('click', function() {
                    var panel = header.closest('.panel');
                    if (!panel.classList.contains('home-panel')) {
                        panel.classList.toggle('panel-collapsed');
                    }
                });
            });
        }
    };

    document.addEventListener('DOMContentLoaded', function() {
        App.init();
    });

    window.PandaApp = App;
})(window, document, jQuery);
