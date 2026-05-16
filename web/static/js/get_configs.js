(function(window, document, $) {
    'use strict';

    var GetConfigs = {
        keys: {
            checkbox: 'panda.get_configs.checkbox',
            groups: 'panda.get_configs.groups',
            hosts: 'panda.get_configs.hosts',
            manualHosts: 'panda.get_configs.manual_hosts',
            excludedHosts: 'panda.get_configs.excluded_hosts',
            targetSource: 'panda.target.source'
        },

        init: function() {
            this.cache();
            this.buildTargetChoices();
            this.restoreState();
            this.bindEvents();
            this.loadStoredTargetSource();
            this.render();
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

            document.getElementById('runScriptBtn').addEventListener('click', function() {
                self.run();
            });

            window.addEventListener('panda:target-source-change', function(event) {
                self.loadTargetSource(event.detail.source);
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
            var lookup = {};
            var groups = this.selectedGroups();
            var hosts = this.selectedHosts();
            var groupLookup = {};

            groups.forEach(function(group) {
                groupLookup[group] = true;
            });

            this.getGroups().forEach(function(group) {
                if (groupLookup[group.value]) {
                    group.devices.forEach(function(device) {
                        lookup[device] = true;
                    });
                }
            });

            hosts.forEach(function(host) {
                lookup[host] = true;
            });

            return Object.keys(lookup).sort();
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

            this.renderReview(info, devices);
            this.renderModal(info, devices);
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
            var assigned = {};
            var blocks = [];
            var hostLookup = {};
            var ungroupedHosts = [];

            this.getHosts().forEach(function(host) {
                hostLookup[host.value] = host;
            });

            selectedGroups.forEach(function(groupName) {
                var group = self.getGroups().find(function(item) {
                    return item.value === groupName;
                });
                var devices = group ? group.devices.slice().sort() : [];

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
            var info = [];
            document.querySelectorAll('#accordion input[type="checkbox"]:checked').forEach(function(input) {
                info.push(input.id);
            });

            $.ajax({
                url: '/run_get_configs',
                type: 'POST',
                contentType: 'application/json',
                data: JSON.stringify({
                    targetSource: this.getTargetSource(),
                    selectedDeviceGroups: this.selectedGroups(),
                    selectedDevices: this.selectedHosts(),
                    informationDataSelected: info
                })
            });
        }
    };

    document.addEventListener('DOMContentLoaded', function() {
        GetConfigs.init();
    });

    window.PandaGetConfigs = GetConfigs;
})(window, document, jQuery);
