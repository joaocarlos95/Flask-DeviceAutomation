(function(window, document, $) {
    'use strict';

    var GetConfigs = {
        keys: {
            checkbox: 'panda.get_configs.checkbox',
            groups: 'panda.get_configs.groups',
            hosts: 'panda.get_configs.hosts',
            manualHosts: 'panda.get_configs.manual_hosts',
            excludedHosts: 'panda.get_configs.excluded_hosts',
            targetSource: 'panda.target.source',
            runId: 'panda.get_configs.run_id'
        },

        init: function() {
            this.cache();
            this.buildTargetChoices();
            this.restoreState();
            this.bindEvents();
            this.switchModalView('confirm');
            this.loadStoredTargetSource();
            this.render();
            this.updateReopenButton(false);
            this.restoreActiveRunState();
        },

        cache: function() {
            this.groupSelect = document.getElementById('device_group_options');
            this.hostSelect = document.getElementById('device_host_options');
            this.groupList = document.getElementById('deviceGroupChoiceList');
            this.hostList = document.getElementById('deviceHostChoiceList');
            this.infoSearch = document.getElementById('informationDataSearch');
            this.targetSearch = document.getElementById('deviceGroupSearch');
            this.infoCount = document.getElementById('informationDataSelectedCount');
            this.targetCount = document.getElementById('targetSelectedCount');
            this.reviewBody = document.getElementById('informationDataSelectedBody');
            this.reviewDataCount = document.getElementById('reviewDataPointCount');
            this.reviewTargetCount = document.getElementById('reviewDeviceGroupCount');
            this.modalDataCount = document.getElementById('modalDataPointCount');
            this.modalTargetCount = document.getElementById('modalTargetCount');
            this.modalInfo = document.getElementById('informationDataModal');
            this.modalTargets = document.getElementById('selectedDeviceGroupsModal');
            this.emptyTargets = document.getElementById('deviceGroupSearchEmpty');
            this.sourceMessage = document.getElementById('targetSourceMessage');
            this.executionRunState = document.getElementById('executionRunState');
            this.executionStatusList = document.getElementById('executionStatusList');
            this.executionRunningCount = document.getElementById('executionRunningCount');
            this.executionSuccessCount = document.getElementById('executionSuccessCount');
            this.executionErrorCount = document.getElementById('executionErrorCount');
            this.executionEventSearch = document.getElementById('executionEventSearch');
            this.executionShowAll = document.getElementById('executionShowAll');
            this.executionShowErrors = document.getElementById('executionShowErrors');
            this.modalOutsidePrev = document.getElementById('modalOutsidePrev');
            this.modalOutsideNext = document.getElementById('modalOutsideNext');
            this.modalShell = document.querySelector('#runGetConfigsModal .modal-shell');
            this.runFixedDialog = document.querySelector('#runGetConfigsModal .run-fixed-dialog');
            this.runModalFixed = document.querySelector('#runGetConfigsModal .run-modal-fixed');
            this.miniConfirmCard = document.getElementById('miniConfirmCard');
            this.miniLogsCard = document.getElementById('miniLogsCard');
            this.miniConfirmDataCount = document.getElementById('miniConfirmDataCount');
            this.miniConfirmTargetCount = document.getElementById('miniConfirmTargetCount');
            this.miniReviewBody = document.getElementById('miniReviewBody');
            this.miniLogsRunCount = document.getElementById('miniLogsRunCount');
            this.miniLogsSuccessCount = document.getElementById('miniLogsSuccessCount');
            this.miniLogsErrorCount = document.getElementById('miniLogsErrorCount');
            this.miniLogsStatus = document.getElementById('miniLogsStatus');
            this.miniLogsBody = document.getElementById('miniLogsBody');
            this.confirmViewPanel = document.getElementById('confirmViewPanel');
            this.logsViewPanel = document.getElementById('logsViewPanel');
            this.modalRunAction = document.querySelector('#runGetConfigsModal .modal-run-action');
            this.runModalFooter = document.getElementById('runModalFooter');
            this.recentRunsWrap = document.getElementById('recentRunsWrap');
            this.recentRunsList = document.getElementById('recentRunsList');
            this.runScriptBtn = document.getElementById('runScriptBtn');
            this.openRunModalBtn = document.getElementById('openRunModalBtn');
            this.reopenExecutionBtn = document.getElementById('reopenExecutionBtn');
            this.activeRunId = null;
            this.statusPollHandle = null;
            this.executionViewMode = 'all';
            this.runActionMode = 'run';
            this.modalView = 'confirm';
            this.modalOpenMode = 'confirm';
            this.latestRunStatus = null;
            this.currentRunTargets = [];
        },

        targetKey: function(key) {
            return key + ':' + this.getTargetSource();
        },

        getTargetSource: function() {
            return this.groupSelect ? this.groupSelect.dataset.targetSource || 'inventory' : 'inventory';
        },

        readJson: function(key, fallback) {
            try {
                return JSON.parse(sessionStorage.getItem(key)) || fallback;
            } catch (error) {
                return fallback;
            }
        },

        writeJson: function(key, value) {
            sessionStorage.setItem(key, JSON.stringify(value));
        },

        getGroups: function() {
            return Array.prototype.map.call(this.groupSelect.options, function(option) {
                return {
                    value: option.value,
                    label: option.textContent.trim(),
                    devices: (option.dataset.devices || '').split(/\s+/).filter(Boolean)
                };
            });
        },

        getHosts: function() {
            return Array.prototype.map.call(this.hostSelect.options, function(option) {
                return {
                    value: option.value,
                    label: option.textContent.trim(),
                    hostname: option.dataset.hostname || '',
                    groups: (option.dataset.groups || '').split(/\s+/).filter(Boolean)
                };
            });
        },

        selectedGroups: function() {
            return Array.prototype.filter.call(this.groupSelect.options, function(option) {
                return option.selected;
            }).map(function(option) {
                return option.value;
            });
        },

        selectedHosts: function() {
            return Array.prototype.filter.call(this.hostSelect.options, function(option) {
                return option.selected;
            }).map(function(option) {
                return option.value;
            });
        },

        setSelected: function(select, values) {
            var lookup = {};
            values.forEach(function(value) {
                lookup[value] = true;
            });
            Array.prototype.forEach.call(select.options, function(option) {
                option.selected = !!lookup[option.value];
            });
        },

        devicesForGroups: function(groupValues) {
            var lookup = {};
            var groups = this.getGroups();
            var selectedLookup = {};

            groupValues.forEach(function(group) {
                selectedLookup[group] = true;
            });

            groups.forEach(function(group) {
                if (!selectedLookup[group.value]) {
                    return;
                }
                group.devices.forEach(function(device) {
                    lookup[device] = true;
                });
            });

            return Object.keys(lookup);
        },

        computeSelectedHostsFromState: function() {
            var selectedLookup = {};
            var excludedLookup = {};
            var groupHosts = this.devicesForGroups(this.selectionState.groups);

            this.selectionState.excludedHosts.forEach(function(host) {
                excludedLookup[host] = true;
            });

            this.selectionState.manualHosts.forEach(function(host) {
                selectedLookup[host] = true;
            });

            groupHosts.forEach(function(host) {
                if (!excludedLookup[host]) {
                    selectedLookup[host] = true;
                }
            });

            return Object.keys(selectedLookup);
        },

        applyTargetState: function() {
            var selectedHosts = this.computeSelectedHostsFromState();
            this.setSelected(this.groupSelect, this.selectionState.groups);
            this.setSelected(this.hostSelect, selectedHosts);
            this.syncChoiceCards();
        },

        buildTargetChoices: function() {
            this.groupList.innerHTML = '';
            this.hostList.innerHTML = '';

            this.getGroups().forEach(this.appendGroupChoice.bind(this));
            this.getHosts().forEach(this.appendHostChoice.bind(this));
            this.updateVisibleCounts();
        },

        appendGroupChoice: function(group) {
            var label = this.createChoice(group.label, group.value, 'group');
            label.dataset.devices = group.devices.join(' ');
            this.groupList.appendChild(label);
        },

        appendHostChoice: function(host) {
            var detail = host.hostname ? document.createElement('small') : null;
            var label = this.createChoice(host.label, host.value, 'host');
            var name = label.querySelector('.choice-name');
            label.dataset.hostname = host.hostname;
            label.dataset.groups = host.groups.join(' ');

            if (detail) {
                detail.textContent = host.hostname;
                name.appendChild(detail);
            }

            this.hostList.appendChild(label);
        },

        createChoice: function(text, value, type) {
            var label = document.createElement('label');
            var input = document.createElement('input');
            var check = document.createElement('span');
            var name = document.createElement('span');

            label.className = 'choice-card';
            label.dataset.value = value;
            label.dataset.type = type;
            input.type = 'checkbox';
            input.value = value;
            check.className = 'choice-check';
            check.innerHTML = '<i class="fas fa-check" aria-hidden="true"></i>';
            name.className = 'choice-name';
            name.textContent = text;

            label.appendChild(input);
            label.appendChild(check);
            label.appendChild(name);

            return label;
        },

        restoreState: function() {
            var checkboxState = this.readJson(this.keys.checkbox, {});
            var selectedGroups = this.readJson(this.targetKey(this.keys.groups), []);
            var selectedHosts = this.readJson(this.targetKey(this.keys.hosts), []);
            var manualHosts = this.readJson(this.targetKey(this.keys.manualHosts), []);
            var excludedHosts = this.readJson(this.targetKey(this.keys.excludedHosts), []);
            var groupHostsLookup = {};

            document.querySelectorAll('#accordion input[type="checkbox"]').forEach(function(input) {
                input.checked = !!checkboxState[input.id];
                input.closest('.choice-card').classList.toggle('selected', input.checked);
                input.closest('.choice-card').classList.toggle('disabled', input.disabled);
            });

            this.devicesForGroups(selectedGroups).forEach(function(host) {
                groupHostsLookup[host] = true;
            });

            if (!manualHosts.length && selectedHosts.length) {
                manualHosts = selectedHosts.filter(function(host) {
                    return !groupHostsLookup[host];
                });
            }

            this.selectionState = {
                groups: selectedGroups.slice(),
                manualHosts: manualHosts.slice(),
                excludedHosts: excludedHosts.slice()
            };

            this.applyTargetState();
        },

        bindEvents: function() {
            var self = this;
            var safeBind = function(element, eventName, handler) {
                if (element) {
                    element.addEventListener(eventName, handler);
                }
            };

            document.querySelectorAll('#accordion input[type="checkbox"]').forEach(function(input) {
                input.addEventListener('change', function() {
                    if (input.disabled) {
                        return;
                    }
                    input.closest('.choice-card').classList.toggle('selected', input.checked);
                    self.saveCheckboxes();
                    self.render();
                });
            });

            document.querySelectorAll('#deviceGroupChoiceList, #deviceHostChoiceList').forEach(function(list) {
                list.addEventListener('change', function(event) {
                    if (event.target.type === 'checkbox') {
                        self.handleTargetChoice(event.target.closest('.choice-card'));
                    }
                });
            });

            document.getElementById('expandInformationData').addEventListener('click', function() {
                self.setSectionsCollapsed('#accordion .choice-section', false);
            });
            document.getElementById('collapseInformationData').addEventListener('click', function() {
                self.setSectionsCollapsed('#accordion .choice-section', true);
            });
            document.getElementById('clearInformationData').addEventListener('click', function() {
                document.querySelectorAll('#accordion input[type="checkbox"]').forEach(function(input) {
                    input.checked = false;
                    input.closest('.choice-card').classList.remove('selected');
                });
                self.saveCheckboxes();
                self.render();
            });

            document.getElementById('expandTargets').addEventListener('click', function() {
                self.setSectionsCollapsed('[data-target-section]', false);
            });
            document.getElementById('collapseTargets').addEventListener('click', function() {
                self.setSectionsCollapsed('[data-target-section]', true);
            });
            document.getElementById('clearTargets').addEventListener('click', function() {
                self.selectionState = {
                    groups: [],
                    manualHosts: [],
                    excludedHosts: []
                };
                self.applyTargetState();
                self.saveTargets();
                self.render();
            });

            this.infoSearch.addEventListener('input', function() {
                self.filterInformation();
            });
            this.targetSearch.addEventListener('input', function() {
                self.filterTargets();
            });

            safeBind(this.runScriptBtn, 'click', function() {
                if (self.runActionMode === 'interrupt') {
                    self.interruptRun();
                    return;
                }
                if (self.modalView === 'logs') {
                    return;
                }
                self.run();
            });
            safeBind(this.executionShowAll, 'click', function() {
                self.executionViewMode = 'all';
                self.executionShowAll.classList.add('active');
                self.executionShowErrors.classList.remove('active');
                self.fetchRunStatus();
            });
            safeBind(this.executionShowErrors, 'click', function() {
                self.executionViewMode = 'errors';
                self.executionShowErrors.classList.add('active');
                self.executionShowAll.classList.remove('active');
                self.fetchRunStatus();
            });
            safeBind(this.executionEventSearch, 'input', function() {
                if (self.latestRunStatus) {
                    self.renderRunStatus(self.latestRunStatus);
                }
            });
            safeBind(this.modalOutsidePrev, 'click', function() { self.switchModalView('confirm'); });
            safeBind(this.modalOutsideNext, 'click', function() { self.switchModalView('logs'); });
            safeBind(this.miniConfirmCard, 'click', function() { self.switchModalView('confirm'); });
            safeBind(this.miniLogsCard, 'click', function() { self.switchModalView('logs'); });
            safeBind(this.openRunModalBtn, 'click', function() {
                self.modalOpenMode = 'confirm';
            });
            safeBind(this.reopenExecutionBtn, 'click', function() {
                if (self.reopenExecutionBtn.disabled) {
                    return;
                }
                self.modalOpenMode = 'logs';
                $('#runGetConfigsModal').modal('show');
                self.switchModalView('logs');
                self.fetchRunStatus();
            });
            if (this.recentRunsList) {
                this.recentRunsList.addEventListener('wheel', function(event) {
                    if (!self.recentRunsList) {
                        return;
                    }
                    if (Math.abs(event.deltaY) > Math.abs(event.deltaX)) {
                        self.recentRunsList.scrollLeft += event.deltaY;
                        event.preventDefault();
                    }
                }, { passive: false });
            }
            window.addEventListener('panda:target-source-change', function(event) {
                self.loadTargetSource(event.detail.source);
            });

            $('#runGetConfigsModal').on('show.bs.modal', function() {
                self.switchModalView(self.modalOpenMode === 'logs' ? 'logs' : 'confirm');
                if (self.runActionMode !== 'interrupt') {
                    self.setRunButtonMode('run');
                }
                self.fetchRecentRuns();
            });
            $('#runGetConfigsModal').on('shown.bs.modal', function() {
                self.alignMiniCards();
            });
            $('#runGetConfigsModal').on('hidden.bs.modal', function() {
                document.body.classList.remove('modal-open');
                $('.modal-backdrop').remove();
                self.updateReopenButton();
            });
            window.addEventListener('resize', function() {
                self.alignMiniCards();
            });
        },

        handleTargetChoice: function(card) {
            var self = this;
            var selectedGroupsLookup = {};
            var nextGroups;

            if (card.dataset.type === 'group') {
                nextGroups = this.selectedValuesFromCards('group');
                this.selectionState.groups.forEach(function(group) {
                    selectedGroupsLookup[group] = true;
                });

                // When a group is selected, reset exclusions for that group's hosts so bulk select is explicit.
                nextGroups.forEach(function(groupName) {
                    var group = self.getGroups().find(function(item) {
                        return item.value === groupName;
                    });

                    if (!group || selectedGroupsLookup[groupName]) {
                        return;
                    }

                    self.selectionState.excludedHosts = self.selectionState.excludedHosts.filter(function(host) {
                        return group.devices.indexOf(host) === -1;
                    });
                });

                this.selectionState.groups = nextGroups;
            }

            if (card.dataset.type === 'host') {
                var hostName = card.dataset.value;
                var hostChecked = !!card.querySelector('input').checked;
                var coveredByGroup = this.devicesForGroups(this.selectionState.groups).indexOf(hostName) !== -1;
                var groupsToKeep = [];
                var selectedHostsLookup = {};
                var groupCoveredLookup = {};

                if (hostChecked) {
                    this.selectionState.excludedHosts = this.selectionState.excludedHosts.filter(function(host) {
                        return host !== hostName;
                    });

                    if (!coveredByGroup && this.selectionState.manualHosts.indexOf(hostName) === -1) {
                        this.selectionState.manualHosts.push(hostName);
                    }
                } else {
                    this.selectionState.manualHosts = this.selectionState.manualHosts.filter(function(host) {
                        return host !== hostName;
                    });

                    if (coveredByGroup && this.selectionState.excludedHosts.indexOf(hostName) === -1) {
                        this.selectionState.excludedHosts.push(hostName);
                    }
                }

                this.computeSelectedHostsFromState().forEach(function(host) {
                    selectedHostsLookup[host] = true;
                });

                this.selectionState.groups.forEach(function(groupName) {
                    var group = self.getGroups().find(function(item) {
                        return item.value === groupName;
                    });

                    if (!group) {
                        return;
                    }

                    var hasSelectedHost = group.devices.some(function(device) {
                        return !!selectedHostsLookup[device];
                    });

                    if (hasSelectedHost) {
                        groupsToKeep.push(groupName);
                        group.devices.forEach(function(device) {
                            groupCoveredLookup[device] = true;
                        });
                    }
                });

                this.selectionState.groups = groupsToKeep;
                this.selectionState.excludedHosts = this.selectionState.excludedHosts.filter(function(host) {
                    return !!groupCoveredLookup[host];
                });
            }

            this.applyTargetState();
            this.saveTargets();
            this.render();
        },

        selectedValuesFromCards: function(type) {
            return Array.prototype.filter.call(document.querySelectorAll('.choice-card[data-type="' + type + '"] input'), function(input) {
                return input.checked;
            }).map(function(input) {
                return input.value;
            });
        },

        syncChoiceCards: function() {
            this.syncChoiceType('group', this.selectedGroups());
            this.syncChoiceType('host', this.selectedHosts());
        },

        syncChoiceType: function(type, values) {
            var lookup = {};
            values.forEach(function(value) {
                lookup[value] = true;
            });
            document.querySelectorAll('.choice-card[data-type="' + type + '"]').forEach(function(card) {
                var checked = !!lookup[card.dataset.value];
                card.classList.toggle('selected', checked);
                card.querySelector('input').checked = checked;
            });
        },

        saveCheckboxes: function() {
            var state = {};
            document.querySelectorAll('#accordion input[type="checkbox"]').forEach(function(input) {
                state[input.id] = input.checked;
            });
            this.writeJson(this.keys.checkbox, state);
        },

        saveTargets: function() {
            this.writeJson(this.targetKey(this.keys.groups), this.selectedGroups());
            this.writeJson(this.targetKey(this.keys.hosts), this.selectedHosts());
            this.writeJson(this.targetKey(this.keys.manualHosts), this.selectionState.manualHosts);
            this.writeJson(this.targetKey(this.keys.excludedHosts), this.selectionState.excludedHosts);
        },

        setSectionsCollapsed: function(selector, collapsed) {
            document.querySelectorAll(selector).forEach(function(section) {
                section.classList.toggle('collapsed', collapsed);
            });
        },

        searchText: function(value) {
            return (value || '').toString().trim().toLowerCase();
        },

        matches: function(text, term) {
            var normalized = this.searchText(text);
            var query = this.searchText(term);
            return !query || query.split(/\s+/).every(function(part) {
                return normalized.indexOf(part) !== -1;
            });
        },

        filterInformation: function() {
            var self = this;
            var term = this.infoSearch.value;
            document.querySelectorAll('#accordion .choice-section').forEach(function(section) {
                var sectionMatches = self.matches(section.dataset.groupName, term);
                var visibleChoices = 0;

                section.querySelectorAll('.choice-card').forEach(function(card) {
                    var visible = sectionMatches || self.matches(card.dataset.choiceLabel || card.textContent, term);
                    card.classList.toggle('hidden', !visible);
                    visibleChoices += visible ? 1 : 0;
                });

                section.classList.toggle('hidden', visibleChoices === 0);
                if (term && visibleChoices > 0) {
                    section.classList.remove('collapsed');
                }
            });
        },

        filterTargets: function() {
            var self = this;
            var term = this.targetSearch.value;
            var visible = 0;

            document.querySelectorAll('#deviceGroupChoiceList .choice-card, #deviceHostChoiceList .choice-card').forEach(function(card) {
                var haystack = [card.textContent, card.dataset.hostname, card.dataset.groups].join(' ');
                var isVisible = self.matches(haystack, term);
                card.classList.toggle('hidden', !isVisible);
                visible += isVisible ? 1 : 0;
            });

            document.querySelectorAll('[data-target-section]').forEach(function(section) {
                var hasVisible = !!section.querySelector('.choice-card:not(.hidden)');
                section.classList.toggle('hidden', !hasVisible);
                if (term && hasVisible) {
                    section.classList.remove('collapsed');
                }
            });

            this.emptyTargets.classList.toggle('visible', visible === 0);
            this.updateVisibleCounts();
        },

        updateVisibleCounts: function() {
            document.getElementById('visibleGroupCount').textContent = document.querySelectorAll('#deviceGroupChoiceList .choice-card:not(.hidden)').length;
            document.getElementById('visibleHostCount').textContent = document.querySelectorAll('#deviceHostChoiceList .choice-card:not(.hidden)').length;
        },

        selectedInformation: function() {
            var groups = {};
            document.querySelectorAll('#accordion .choice-section').forEach(function(section) {
                var labels = [];
                section.querySelectorAll('input[type="checkbox"]:checked').forEach(function(input) {
                    labels.push(input.closest('.choice-card').textContent.trim());
                });
                if (labels.length) {
                    groups[section.dataset.groupName] = labels;
                }
            });
            return groups;
        },

        countInformation: function(info) {
            return Object.keys(info).reduce(function(total, group) {
                return total + info[group].length;
            }, 0);
        },

        selectedTargetDevices: function() {
            return this.selectedHosts().slice().sort();
        },

        getRunTargetDevices: function() {
            var lookup = {};
            var excludedLookup = {};
            var devices = [];
            var self = this;

            (this.selectionState.excludedHosts || []).forEach(function(host) {
                excludedLookup[host] = true;
            });

            this.devicesForGroups(this.selectionState.groups || []).forEach(function(host) {
                if (!excludedLookup[host]) {
                    lookup[host] = true;
                }
            });

            (this.selectionState.manualHosts || []).forEach(function(host) {
                if (!excludedLookup[host]) {
                    lookup[host] = true;
                }
            });

            Object.keys(lookup).forEach(function(host) {
                devices.push(host);
            });

            devices.sort();
            return devices;
        },

        render: function() {
            var info = this.selectedInformation();
            var infoCount = this.countInformation(info);
            var devices = this.selectedTargetDevices();

            this.infoCount.textContent = infoCount;
            this.targetCount.textContent = devices.length;
            this.reviewDataCount.textContent = infoCount;
            this.reviewTargetCount.textContent = devices.length;
            this.modalDataCount.textContent = infoCount;
            this.modalTargetCount.textContent = devices.length;
            if (this.miniConfirmDataCount) {
                this.miniConfirmDataCount.textContent = infoCount;
            }
            if (this.miniConfirmTargetCount) {
                this.miniConfirmTargetCount.textContent = devices.length;
            }
            this.renderMiniPreviews(this.flattenInformation(info), devices);

            this.renderReview(info, devices);
            this.renderModal(info, devices);
        },

        renderMiniPreviews: function(dataItems, targetItems) {
            var dataList = dataItems && dataItems.length ? dataItems : ['No information data selected'];
            var targetList = targetItems && targetItems.length ? targetItems : ['No target devices selected'];
            var html = '';

            if (!this.miniReviewBody) {
                return;
            }

            html =
                '<div class="mini-review-section">' +
                '<span class="mini-label"><i class="fas fa-sliders" aria-hidden="true"></i> Information Data</span>' +
                '<div class="mini-review-list mini-review-list-clean">' + this.renderMiniCleanList(dataList) + '</div>' +
                '</div>' +
                '<div class="mini-review-section">' +
                '<span class="mini-label"><i class="fas fa-network-wired" aria-hidden="true"></i> Target Devices</span>' +
                '<div class="mini-review-list mini-review-list-clean">' + this.renderMiniCleanList(targetList) + '</div>' +
                '</div>';

            this.miniReviewBody.innerHTML = html;
        },

        toMiniPill: function(item) {
            return '<div class="mini-review-pill">' + this.escapeHtml(item) + '</div>';
        },

        renderMiniCleanList: function(items) {
            return items.map(function(item) {
                return '<div class="mini-review-line-item">' + this.escapeHtml(item) + '</div>';
            }.bind(this)).join('');
        },

        escapeHtml: function(value) {
            return String(value || '')
                .replace(/&/g, '&amp;')
                .replace(/</g, '&lt;')
                .replace(/>/g, '&gt;')
                .replace(/"/g, '&quot;')
                .replace(/'/g, '&#39;');
        },

        renderReview: function(info, devices) {
            var dataPoints = this.flattenInformation(info);
            var categories = Object.keys(info);
            this.reviewBody.innerHTML = '';
            this.reviewBody.appendChild(this.buildReviewSection('fa-sliders', 'Information data', [
                this.buildBlock('Data points', dataPoints, 'No data points selected'),
                this.buildBlock('Categories', categories, 'No categories selected')
            ]));
            this.reviewBody.appendChild(this.buildReviewSection('fa-network-wired', 'Target devices', [
                this.buildBlock('Groups', this.selectedGroups(), 'No groups selected'),
                this.buildBlock('Hosts', this.selectedHosts(), 'No hosts selected')
            ]));
        },

        renderModal: function(info, devices) {
            this.modalInfo.innerHTML = '';
            this.modalTargets.innerHTML = '';
            this.buildInfoBlocks(info).forEach(this.modalInfo.appendChild.bind(this.modalInfo));
            this.buildTargetDeviceBlocks().forEach(this.modalTargets.appendChild.bind(this.modalTargets));
        },

        buildReviewSection: function(icon, title, blocks) {
            var section = document.createElement('section');
            var heading = document.createElement('div');

            section.className = 'review-section';
            heading.className = 'review-section-title';
            heading.innerHTML = '<i class="fas ' + icon + '" aria-hidden="true"></i>' + title;
            section.appendChild(heading);
            blocks.forEach(section.appendChild.bind(section));

            return section;
        },

        buildInfoBlocks: function(info) {
            var self = this;
            var groups = Object.keys(info);

            if (!groups.length) {
                return [this.buildBlock('Data points', [], 'No data points selected')];
            }

            return groups.map(function(group) {
                return self.buildBlock(group, info[group], 'No data points selected');
            });
        },

        buildTargetDeviceBlocks: function() {
            var self = this;
            var selectedGroups = this.selectedGroups();
            var selectedHosts = this.selectedHosts();
            var selectedHostLookup = {};
            var assigned = {};
            var blocks = [];
            var hostLookup = {};
            var ungroupedHosts = [];

            this.getHosts().forEach(function(host) {
                hostLookup[host.value] = host;
            });

            selectedHosts.forEach(function(hostName) {
                selectedHostLookup[hostName] = true;
            });

            selectedGroups.forEach(function(groupName) {
                var group = self.getGroups().find(function(item) {
                    return item.value === groupName;
                });
                var devices = group
                    ? group.devices.filter(function(device) {
                        return !!selectedHostLookup[device];
                    }).slice().sort()
                    : [];

                devices.forEach(function(device) {
                    assigned[device] = true;
                });

                blocks.push(self.buildBlock(groupName, devices, 'No devices found in this group'));
            });

            selectedHosts.forEach(function(hostName) {
                var host = hostLookup[hostName];

                if (assigned[hostName]) {
                    return;
                }

                if (!host || !host.groups.length) {
                    ungroupedHosts.push(hostName);
                    assigned[hostName] = true;
                    return;
                }

                host.groups.some(function(groupName) {
                    var existing = blocks.find(function(block) {
                        return block.dataset.blockTitle === groupName;
                    });

                    if (existing) {
                        self.addPill(existing.querySelector('.pill-list'), hostName);
                        self.updateBlockCount(existing);
                    } else {
                        blocks.push(self.buildBlock(groupName, [hostName], 'No devices found in this group'));
                    }

                    assigned[hostName] = true;
                    return true;
                });
            });

            if (ungroupedHosts.length) {
                blocks.push(this.buildBlock('Individual hosts', ungroupedHosts.sort(), 'No hosts selected'));
            }

            if (!blocks.length) {
                return [this.buildBlock('Target devices', [], 'No target devices selected')];
            }

            return blocks;
        },

        flattenInformation: function(info) {
            return Object.keys(info).reduce(function(items, group) {
                return items.concat(info[group]);
            }, []);
        },

        buildBlock: function(title, items, emptyText) {
            var block = document.createElement('div');
            var header = document.createElement('div');
            var count = document.createElement('span');

            block.className = 'review-block';
            block.dataset.blockTitle = title;
            header.className = 'review-block-header';
            header.appendChild(document.createTextNode(title));
            count.className = 'section-meta';
            count.textContent = items.length;
            header.appendChild(count);
            block.appendChild(header);
            block.appendChild(this.buildPills(items, emptyText));
            return block;
        },

        addPill: function(list, item) {
            var empty = list.querySelector('.pill-empty');
            var pill = document.createElement('span');

            if (empty) {
                empty.remove();
            }

            pill.className = 'pill';
            pill.textContent = item;
            list.appendChild(pill);
        },

        updateBlockCount: function(block) {
            var count = block.querySelector('.review-block-header .section-meta');
            count.textContent = block.querySelectorAll('.pill').length;
        },

        buildPills: function(items, emptyText) {
            var list = document.createElement('div');
            list.className = 'pill-list';

            if (!items.length) {
                var empty = document.createElement('span');
                empty.className = 'pill-empty';
                empty.textContent = emptyText;
                list.appendChild(empty);
                return list;
            }

            items.forEach(function(item) {
                var pill = document.createElement('span');
                pill.className = 'pill';
                pill.textContent = item;
                list.appendChild(pill);
            });

            return list;
        },

        loadStoredTargetSource: function() {
            var source = sessionStorage.getItem(this.keys.targetSource);
            if (source && source !== this.getTargetSource()) {
                this.loadTargetSource(source);
            }
        },

        loadTargetSource: function(source) {
            var self = this;

            if (!this.groupSelect || source === this.getTargetSource()) {
                return;
            }

            $.ajax({
                url: '/target_options',
                data: {source: source},
                success: function(data) {
                    if (self.sourceMessage) {
                        self.sourceMessage.textContent = data.error || '';
                        self.sourceMessage.classList.toggle('visible', !!data.error);
                    }
                    self.replaceTargets(data);
                },
                error: function(xhr) {
                    var data = xhr.responseJSON;

                    if (data && data.source) {
                        if (self.sourceMessage) {
                            self.sourceMessage.textContent = data.error || '';
                            self.sourceMessage.classList.toggle('visible', !!data.error);
                        }
                        self.replaceTargets(data);
                        return;
                    }

                    if (self.sourceMessage) {
                        self.sourceMessage.textContent = 'Could not load target source.';
                        self.sourceMessage.classList.add('visible');
                    }
                    self.setSourceButtonState(source);
                    self.render();
                }
            });
        },

        replaceTargets: function(data) {
            var groupDevices = data.group_devices || {};

            this.groupSelect.innerHTML = '';
            this.hostSelect.innerHTML = '';
            this.groupSelect.dataset.targetSource = data.source || 'inventory';
            this.setSourceButtonState(this.groupSelect.dataset.targetSource);
            Object.keys(groupDevices).forEach(function(group) {
                var option = document.createElement('option');
                option.value = group;
                option.textContent = group;
                option.dataset.devices = (groupDevices[group] || []).join(' ');
                this.groupSelect.appendChild(option);
            }, this);
            (data.inventory_hosts || []).forEach(function(host) {
                var option = document.createElement('option');
                option.value = host.name;
                option.textContent = host.name;
                option.dataset.hostname = host.hostname || '';
                option.dataset.groups = (host.groups || []).join(' ');
                this.hostSelect.appendChild(option);
            }, this);
            this.buildTargetChoices();
            this.restoreState();
            this.render();
        },

        setSourceButtonState: function(source) {
            sessionStorage.setItem(this.keys.targetSource, source);

            if (window.PandaApp && typeof window.PandaApp.updateTargetSourceButtons === 'function') {
                window.PandaApp.updateTargetSourceButtons(source);
                return;
            }

            document.querySelectorAll('[data-source-current]').forEach(function(label) {
                label.textContent = source === 'netbox' ? 'NetBox' : 'Inventory';
            });
        },

        run: function() {
            var self = this;
            var info = [];
            var runDevices = this.getRunTargetDevices();
            document.querySelectorAll('#accordion input[type="checkbox"]:checked').forEach(function(input) {
                info.push(input.id);
            });

            this.executionRunState.textContent = 'Starting run...';
            this.executionStatusList.innerHTML = '';
            this.executionRunningCount.textContent = '0';
            this.executionSuccessCount.textContent = '0';
            this.executionErrorCount.textContent = '0';
            if (this.executionEventSearch) {
                this.executionEventSearch.value = '';
            }
            this.latestRunStatus = null;
            this.currentRunTargets = runDevices.slice();
            this.executionViewMode = 'all';
            this.executionShowAll.classList.add('active');
            this.executionShowErrors.classList.remove('active');
            this.setRunButtonMode('interrupt');
            this.switchModalView('logs');
            this.updateReopenButton(true);

            $.ajax({
                url: '/run_get_configs',
                type: 'POST',
                contentType: 'application/json',
                data: JSON.stringify({
                    targetSource: this.getTargetSource(),
                    selectedDeviceGroups: this.selectedGroups(),
                    selectedDevices: runDevices,
                    excludedDevices: this.selectionState.excludedHosts.slice(),
                    informationDataSelected: info
                }),
                success: function(data) {
                    self.activeRunId = data.runId;
                    sessionStorage.setItem(self.keys.runId, data.runId);
                    self.executionRunState.textContent = 'Run started. Collecting command statuses...';
                    self.updateReopenButton(true);
                    self.fetchRecentRuns();
                    self.startStatusPolling();
                },
                error: function(xhr) {
                    var message = 'Could not start run.';
                    if (xhr && xhr.responseJSON && xhr.responseJSON.error) {
                        message = xhr.responseJSON.error;
                    }
                    self.executionRunState.textContent = message;
                }
            });
        },

        switchModalView: function(viewName) {
            var showConfirm = viewName === 'confirm';
            this.modalView = viewName;
            if (this.modalShell) {
                this.modalShell.setAttribute('data-view', showConfirm ? 'confirm' : 'logs');
            }
            if (this.confirmViewPanel) {
                this.confirmViewPanel.classList.toggle('is-hidden', !showConfirm);
            }
            if (this.logsViewPanel) {
                this.logsViewPanel.classList.toggle('is-hidden', showConfirm);
            }
            if (this.modalOutsidePrev) {
                this.modalOutsidePrev.disabled = showConfirm;
            }
            if (this.modalOutsideNext) {
                this.modalOutsideNext.disabled = !showConfirm;
            }
            if (this.miniConfirmCard) {
                this.miniConfirmCard.classList.add('is-hidden');
            }
            if (this.miniLogsCard) {
                this.miniLogsCard.classList.add('is-hidden');
            }
            if (showConfirm) {
                if (this.miniLogsCard) {
                    this.miniLogsCard.classList.remove('is-hidden');
                }
            } else {
                if (this.miniConfirmCard) {
                    this.miniConfirmCard.classList.remove('is-hidden');
                }
            }
            if (this.modalRunAction) {
                this.modalRunAction.classList.remove('is-hidden');
            }
            if (this.recentRunsWrap) {
                this.recentRunsWrap.classList.toggle('is-hidden', showConfirm);
            }
            if (this.runModalFooter) {
                this.runModalFooter.setAttribute('data-view', showConfirm ? 'confirm' : 'logs');
            }
            if (this.runScriptBtn && this.runActionMode !== 'interrupt') {
                this.runScriptBtn.disabled = !showConfirm;
            }
            this.alignMiniCards();
        },

        alignMiniCards: function() {
            var modal = document.getElementById('runGetConfigsModal');
            var overlap = 0;
            var insetY = 10;
            var setCardPos = function(card, left, top, height) {
                if (!card) {
                    return;
                }
                card.style.left = Math.max(8, Math.round(left)) + 'px';
                card.style.top = Math.round(top + insetY) + 'px';
                card.style.transform = 'none';
                card.style.height = Math.round(Math.max(420, height - (insetY * 2))) + 'px';
                card.style.minHeight = Math.round(Math.max(420, height - (insetY * 2))) + 'px';
            };

            if (!modal || !modal.classList.contains('show')) {
                return;
            }

            if (window.innerWidth <= 900) {
                return;
            }

            var anchor = this.runModalFixed || this.runFixedDialog;
            if (!anchor) {
                return;
            }

            var rect = anchor.getBoundingClientRect();
            if (!rect.width || !rect.height) {
                return;
            }

            if (this.miniConfirmCard) {
                var confirmWidth = this.miniConfirmCard.offsetWidth || 260;
                setCardPos(this.miniConfirmCard, rect.left - confirmWidth + overlap, rect.top, rect.height);
            }
            if (this.miniLogsCard) {
                setCardPos(this.miniLogsCard, rect.right - overlap, rect.top, rect.height);
            }
        },

        setRunButtonMode: function(mode) {
            this.runActionMode = mode;
            if (mode === 'interrupt') {
                this.runScriptBtn.classList.remove('primary-button');
                this.runScriptBtn.classList.add('secondary-button');
                this.runScriptBtn.innerHTML = '<i class="fas fa-stop" aria-hidden="true"></i>Stop';
                this.runScriptBtn.disabled = false;
            } else {
                this.runScriptBtn.classList.remove('secondary-button');
                this.runScriptBtn.classList.add('primary-button');
                this.runScriptBtn.innerHTML = '<i class="fas fa-play" aria-hidden="true"></i>Run';
                this.runScriptBtn.disabled = this.modalView === 'logs';
            }
        },

        interruptRun: function() {
            var self = this;
            if (!this.activeRunId) {
                return;
            }
            $.ajax({
                url: '/run_get_configs_interrupt/' + this.activeRunId,
                type: 'POST',
                success: function() {
                    self.executionRunState.textContent = 'Stop requested (interrupt)...';
                    self.setRunButtonMode('run');
                },
                error: function() {
                    self.executionRunState.textContent = 'Could not request interrupt.';
                }
            });
        },

        startStatusPolling: function() {
            var self = this;

            if (this.statusPollHandle) {
                window.clearInterval(this.statusPollHandle);
                this.statusPollHandle = null;
            }

            this.statusPollHandle = window.setInterval(function() {
                self.fetchRunStatus();
            }, 1000);

            this.fetchRunStatus();
        },

        fetchRunStatus: function() {
            var self = this;
            if (!this.activeRunId) {
                return;
            }

            $.ajax({
                url: '/run_get_configs_status/' + this.activeRunId,
                type: 'GET',
                success: function(data) {
                    self.renderRunStatus(data);
                    if (data.status !== 'running') {
                        window.clearInterval(self.statusPollHandle);
                        self.statusPollHandle = null;
                        self.setRunButtonMode('run');
                        self.updateReopenButton(true);
                        self.fetchRecentRuns();
                    }
                },
                error: function() {
                    self.executionRunState.textContent = 'Could not read run status.';
                    if (self.statusPollHandle) {
                        window.clearInterval(self.statusPollHandle);
                        self.statusPollHandle = null;
                    }
                    self.setRunButtonMode('run');
                    self.updateReopenButton(true);
                    sessionStorage.removeItem(self.keys.runId);
                }
            });
        },

        renderRunStatus: function(statusData) {
            var self = this;
            var events = statusData.events || [];
            var failedEvents = events.filter(function(event) {
                return ((event.status || '').toLowerCase() === 'error');
            });
            var statusLabel = statusData.status || 'running';
            var searchText = this.executionEventSearch ? (this.executionEventSearch.value || '').trim().toLowerCase() : '';
            var selectedDevices = this.currentRunTargets && this.currentRunTargets.length
                ? this.currentRunTargets
                : this.selectedHosts();
            var deviceStats = this.buildDeviceStats(events, selectedDevices);
            this.latestRunStatus = statusData;

            if (statusLabel === 'completed') {
                this.executionRunState.textContent = 'Completed successfully.';
            } else if (statusLabel === 'failed') {
                this.executionRunState.textContent = 'Failed: ' + (statusData.error || 'Unknown error');
            } else if (statusLabel === 'interrupted') {
                this.executionRunState.textContent = 'Interrupted by user.';
            } else {
                this.executionRunState.textContent = 'Running...';
            }

            this.executionRunningCount.textContent = deviceStats.running;
            this.executionSuccessCount.textContent = deviceStats.success;
            this.executionErrorCount.textContent = deviceStats.error;
            if (this.miniLogsStatus) {
                this.miniLogsStatus.textContent = String(statusLabel || 'idle').toUpperCase();
            }
            if (this.miniLogsRunCount) {
                this.miniLogsRunCount.textContent = deviceStats.running;
            }
            if (this.miniLogsSuccessCount) {
                this.miniLogsSuccessCount.textContent = deviceStats.success;
            }
            if (this.miniLogsErrorCount) {
                this.miniLogsErrorCount.textContent = deviceStats.error;
            }
            this.renderMiniLogsPreview(statusData, deviceStats);
            this.alignMiniCards();

            this.executionStatusList.innerHTML = '';
            var listToRender = this.executionViewMode === 'errors' ? failedEvents : events;
            if (searchText) {
                listToRender = listToRender.filter(function(event) {
                    return self.matchExecutionEvent(event, searchText);
                });
            }

            listToRender.slice(-250).forEach(function(event) {
                var pill = document.createElement('span');
                var status = (event.status || '').toLowerCase();
                var icon = status === 'error' ? '✗' : (status === 'success' ? '✓' : '…');
                pill.className = 'pill status-' + status;
                pill.textContent =
                    '[' + (event.timestamp || '') + '] ' +
                    icon + ' ' +
                    (event.device || '-') + ' (' + (event.ip || '-') + ') ' +
                    (event.config_info || '-') + ' :: ' + (event.command || '-') + ' - ' + (event.message || '');
                self.executionStatusList.appendChild(pill);
            });
        },

        updateReopenButton: function(hasRunStarted) {
            if (!this.reopenExecutionBtn) {
                return;
            }
            var enabled = !!hasRunStarted || !!this.activeRunId;
            this.reopenExecutionBtn.disabled = !enabled;
            this.reopenExecutionBtn.classList.toggle('is-disabled', !enabled);
            this.reopenExecutionBtn.classList.toggle('is-active', enabled);
        },

        restoreActiveRunState: function() {
            var storedRunId = sessionStorage.getItem(this.keys.runId);
            var self = this;
            if (!storedRunId) {
                this.fetchRecentRuns();
                return;
            }
            this.activeRunId = storedRunId;
            this.updateReopenButton(true);
            $.ajax({
                url: '/run_get_configs_status/' + storedRunId,
                type: 'GET',
                success: function(data) {
                    self.latestRunStatus = data;
                    self.renderRunStatus(data);
                    self.fetchRecentRuns();
                    if (data.status === 'running') {
                        self.startStatusPolling();
                    } else {
                        self.setRunButtonMode('run');
                        self.updateReopenButton(true);
                    }
                },
                error: function() {
                    self.activeRunId = null;
                    self.updateReopenButton(false);
                    sessionStorage.removeItem(self.keys.runId);
                }
            });
        },

        fetchRecentRuns: function() {
            var self = this;
            if (!this.recentRunsList) {
                return;
            }
            $.ajax({
                url: '/run_get_configs_recent',
                type: 'GET',
                success: function(data) {
                    self.renderRecentRuns((data && data.runs) || []);
                }
            });
        },

        renderRecentRuns: function(runs) {
            var self = this;
            if (!this.recentRunsList) {
                return;
            }

            this.recentRunsList.innerHTML = '';
            if (!runs.length) {
                var empty = document.createElement('span');
                empty.className = 'recent-run-empty';
                empty.textContent = 'No runs yet';
                this.recentRunsList.appendChild(empty);
                return;
            }

            runs.slice(0, 8).forEach(function(run) {
                var button = document.createElement('button');
                var startedAt = run.startedAt ? new Date(run.startedAt * 1000) : null;
                var hh = startedAt ? String(startedAt.getHours()).padStart(2, '0') : '--';
                var mm = startedAt ? String(startedAt.getMinutes()).padStart(2, '0') : '--';
                var status = (run.status || 'unknown').toLowerCase();

                button.type = 'button';
                button.className = 'btn secondary-button btn-sm recent-run-btn status-' + status;
                if (run.runId === self.activeRunId) {
                    button.classList.add('active');
                }
                button.textContent = hh + ':' + mm + ' ' + status;
                button.addEventListener('click', function() {
                    self.activeRunId = run.runId;
                    sessionStorage.setItem(self.keys.runId, run.runId);
                    self.modalOpenMode = 'logs';
                    self.switchModalView('logs');
                    self.fetchRunStatus();
                    self.updateReopenButton(true);
                    self.fetchRecentRuns();
                });
                self.recentRunsList.appendChild(button);
            });
        },

        matchExecutionEvent: function(event, searchText) {
            if (!searchText) {
                return true;
            }
            var eventText = [
                event.timestamp || '',
                event.status || '',
                event.device || '',
                event.ip || '',
                event.config_info || '',
                event.command || '',
                event.message || ''
            ].join(' ').toLowerCase();
            return eventText.indexOf(searchText) !== -1;
        },

        buildDeviceStats: function(events, selectedDevices) {
            var states = {};
            var stats = { running: 0, success: 0, error: 0 };

            selectedDevices.forEach(function(device) {
                states[device] = 'pending';
            });

            events.forEach(function(event) {
                var device = event.device || '';
                var status = (event.status || '').toLowerCase();
                var previous = states[device];

                if (!device || device === '-') {
                    return;
                }

                if (typeof previous === 'undefined') {
                    states[device] = 'pending';
                    previous = 'pending';
                }

                if (status === 'error') {
                    states[device] = 'error';
                    return;
                }

                if (status === 'running') {
                    if (previous !== 'error') {
                        states[device] = 'running';
                    }
                    return;
                }

                if (status === 'success') {
                    if (previous !== 'error') {
                        states[device] = 'success';
                    }
                }
            });

            Object.keys(states).forEach(function(device) {
                var state = states[device];
                if (state === 'running') {
                    stats.running += 1;
                } else if (state === 'success') {
                    stats.success += 1;
                } else if (state === 'error') {
                    stats.error += 1;
                }
            });

            return stats;
        },

        latestEventCompact: function(events) {
            if (!events || !events.length) {
                return 'No execution events yet';
            }
            var event = events[events.length - 1];
            var ts = event.timestamp || '';
            var status = (event.status || 'info').toUpperCase();
            var message = event.message || '';
            return '[' + ts + '] ' + status + ' - ' + message;
        },

        renderMiniLogsPreview: function(statusData, deviceStats) {
            var events = (statusData && statusData.events) ? statusData.events : [];
            var stats = deviceStats || this.buildDeviceStats(events, this.currentRunTargets || []);
            var recent = events.slice().reverse();
            var statusLabel = (statusData && statusData.status ? String(statusData.status) : 'idle').toUpperCase();
            var durationLabel = this.getMiniRunDuration(statusData, events);
            var html = '';
            var items = [];

            if (!this.miniLogsBody) {
                return;
            }

            items = recent.slice(0, 10);

            html =
                '<div class="mini-logs-layout">' +
                '<div class="mini-logs-status">' +
                '<strong>' + this.escapeHtml(statusLabel) + '</strong>' +
                '<span>' + this.escapeHtml(durationLabel) + '</span>' +
                '</div>' +
                '<div class="mini-logs-health">' +
                '<div class="mini-logs-health-item"><strong>' + this.escapeHtml(String(stats.running)) + '</strong><span>Running</span></div>' +
                '<div class="mini-logs-health-item"><strong>' + this.escapeHtml(String(stats.success)) + '</strong><span>Success</span></div>' +
                '<div class="mini-logs-health-item"><strong>' + this.escapeHtml(String(stats.error)) + '</strong><span>Errors</span></div>' +
                '</div>' +
                '<span class="mini-label">Event summary</span>' +
                '<div class="mini-review-list mini-review-list-clean mini-logs-events">' +
                (items.length ? items.map(function(event) {
                    return '<div class="mini-review-line-item ' + this.getMiniEventClass(event) + '">' + this.escapeHtml(this.formatMiniEventLine(event)) + '</div>';
                }.bind(this)).join('') : '<div class="mini-review-line-item">No execution events yet</div>') +
                '</div>' +
                '</div>';

            this.miniLogsBody.innerHTML = html;
        },

        getMiniRunDuration: function(statusData, events) {
            var data = statusData || {};
            var value = data.duration || data.duration_seconds || data.durationSeconds;
            var seconds = Number(value);

            if (!Number.isNaN(seconds) && seconds > 0) {
                return 'Duration: ' + Math.round(seconds) + 's';
            }

            var candidate = (events || []).slice().reverse().find(function(event) {
                return /execution time/i.test(String(event.message || ''));
            });

            if (candidate && candidate.message) {
                return 'Duration: ' + String(candidate.message).replace(/^.*Execution time:\s*/i, '');
            }

            return 'Duration: -';
        },

        formatMiniEventLine: function(event) {
            var ts = event && event.timestamp ? String(event.timestamp) : '';
            var status = event && event.status ? String(event.status).toUpperCase() : 'INFO';
            var device = event && event.device ? String(event.device) : '-';
            var message = event && event.message ? String(event.message) : '';
            var shortMessage = message.split('\n')[0].split('. ')[0].trim();

            if (shortMessage.length > 64) {
                shortMessage = shortMessage.slice(0, 61) + '...';
            }
            if (!shortMessage) {
                shortMessage = '-';
            }

            return '[' + ts + '] ' + status + ' ' + device + ' - ' + shortMessage;
        },

        getMiniEventClass: function(event) {
            var status = String((event && event.status) || '').toLowerCase();
            if (status === 'error') {
                return 'mini-event-error';
            }
            if (status === 'success') {
                return 'mini-event-success';
            }
            if (status === 'running') {
                return 'mini-event-running';
            }
            return 'mini-event-info';
        },

        latestEventField: function(events, fieldName, fallback) {
            if (!events || !events.length) {
                return fallback;
            }
            var event = events[events.length - 1];
            var value = event[fieldName];
            if (!value || value === '-') {
                return fallback;
            }
            return String(value);
        }
    };

    document.addEventListener('DOMContentLoaded', function() {
        GetConfigs.init();
    });

    window.PandaGetConfigs = GetConfigs;
})(window, document, jQuery);

