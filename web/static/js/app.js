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
            this.browserUp = document.getElementById('folderBrowserUp');
            this.useFolder = document.getElementById('useCurrentFolder');
            this.saveSettings = document.getElementById('saveTargetSettings');
            this.settingsMessage = document.getElementById('targetSettingsMessage');
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
                    self.loadFolder(self.inventoryInput.value);
                });
            }

            if (this.browserUp) {
                this.browserUp.addEventListener('click', function() {
                    if (self.browserUp.dataset.path) {
                        self.loadFolder(self.browserUp.dataset.path);
                    }
                });
            }

            if (this.useFolder && this.inventoryInput) {
                this.useFolder.addEventListener('click', function() {
                    self.inventoryInput.value = self.useFolder.dataset.path || self.inventoryInput.value;
                });
            }
        },

        loadFolder: function(path) {
            var self = this;

            $.ajax({
                url: '/browse_folders',
                data: {path: path},
                success: function(data) {
                    self.renderFolders(data);
                },
                error: function() {
                    self.showSettingsMessage('Could not open that folder.');
                }
            });
        },

        renderFolders: function(data) {
            var self = this;

            if (!this.browser || !this.browserList || !this.browserPath || !this.browserUp || !this.useFolder) {
                return;
            }

            this.browser.hidden = false;
            this.browserPath.textContent = data.currentPath;
            this.browserUp.disabled = !data.parentPath;
            this.browserUp.dataset.path = data.parentPath || '';
            this.useFolder.dataset.path = data.currentPath;
            this.useFolder.textContent = data.hasInventoryFiles ? 'Use this inventory folder' : 'Use this folder';
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

            button.type = 'button';
            button.className = 'folder-option';
            name.textContent = folder.name;
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

        bindSettings: function() {
            var self = this;

            if (!this.saveSettings) {
                return;
            }

            this.saveSettings.addEventListener('click', function() {
                $.ajax({
                    url: '/target_settings',
                    type: 'POST',
                    contentType: 'application/json',
                    data: JSON.stringify({
                        rootDirectory: self.inventoryInput ? self.inventoryInput.value : '',
                        netboxUrl: document.getElementById('netboxUrl').value,
                        netboxToken: document.getElementById('netboxToken').value
                    }),
                    success: function() {
                        self.showSettingsMessage('Settings saved.');
                    },
                    error: function() {
                        self.showSettingsMessage('Could not save settings.');
                    }
                });
            });
        },

        showSettingsMessage: function(text) {
            if (!this.settingsMessage) {
                return;
            }

            this.settingsMessage.textContent = text;
            this.settingsMessage.classList.add('visible');
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
