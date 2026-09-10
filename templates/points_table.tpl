% hostname_safe = "".join([c if c.isalnum() else "-" for c in hostname])
<div style="display: flex; gap: 15px; flex-wrap: wrap; margin-bottom: 20px; align-items: flex-end;">
    <div class="form-group" style="margin-bottom: 0;">
        <label style="font-size: 0.75rem;">Protocole :</label>
        <select id="filter-proto-{{hostname_safe}}" onchange="filterTable('{{hostname_safe}}')" class="input-dark" style="min-width: 100px;">
            <option value="">Tous</option>
            % for proto in sorted(list(set(str(p['protocol']) for p in points))):
            <option value="{{proto}}">{{proto}}</option>
            % end
        </select>
    </div>
    <div class="form-group" style="margin-bottom: 0;">
        <label style="font-size: 0.75rem;">Device :</label>
        <div style="display: flex; gap: 10px;">
            <select id="filter-dev-{{hostname_safe}}" onchange="onDeviceFilterChange('{{hostname_safe}}'); filterTable('{{hostname_safe}}')" class="input-dark" style="min-width: 140px;">
                <option value="">Tous les équipements</option>
                % for dev in sorted(list(set(str(p['device']) for p in points))):
                <option value="{{dev}}">{{dev}}</option>
                % end
            </select>
            <button id="btn-purge-dev-{{hostname_safe}}"
                    type="button"
                    data-chantier-id="{{chantier['id']}}"
                    data-hostname="{{hostname}}"
                    data-hostname-safe="{{hostname_safe}}"
                    onclick="purgeSelectedDeviceFromFilter(this)"
                    class="btn-danger btn-sm"
                    style="display: none;"
                    title="Purger tous les relevés de cet équipement">
                <span class="material-symbols-outlined icon-sm">delete</span>
            </button>
        </div>
    </div>
    <div class="form-group" style="margin-bottom: 0; flex-grow: 1;">
        <label style="font-size: 0.75rem;">Recherche dans les points :</label>
        <div style="position: relative;">
            <span class="material-symbols-outlined" style="position: absolute; left: 10px; top: 50%; transform: translateY(-50%); color: var(--outline); font-size: 18px;">search</span>
            <input type="text" id="filter-search-{{hostname_safe}}" onkeyup="filterTable('{{hostname_safe}}')" placeholder="Mots-clés (ex: Température, Consigne)..." class="input-dark" style="padding-left: 35px;">
        </div>
    </div>
</div>

<div class="table-scroll" style="max-height: 600px;">
    <table id="table-{{hostname_safe}}" class="data-table">
        <thead>
            <tr>
                <th style="cursor: pointer;" onclick="window.sortTable('table-{{hostname_safe}}', 0, 'str', this)">Protocole <span class="sort-icon"></span></th>
                <th style="cursor: pointer;" onclick="window.sortTable('table-{{hostname_safe}}', 1, 'str', this)">Équipement <span class="sort-icon"></span></th>
                <th style="cursor: pointer;" onclick="window.sortTable('table-{{hostname_safe}}', 2, 'str', this)">Objet / Registre <span class="sort-icon"></span></th>
                <th style="cursor: pointer;" onclick="window.sortTable('table-{{hostname_safe}}', 3, 'str', this)">Description <span class="sort-icon"></span></th>
                <th style="text-align: right; cursor: pointer;" onclick="window.sortTable('table-{{hostname_safe}}', 4, 'num', this)">Valeur <span class="sort-icon"></span></th>
                <th style="text-align: center; cursor: pointer;" onclick="window.sortTable('table-{{hostname_safe}}', 5, 'num', this)">Relevés <span class="sort-icon"></span></th>
                <th style="width: 40px;"></th>
            </tr>
        </thead>
        <tbody>
            % for p in points:
            <tr data-protocol="{{p['protocol']}}" data-device="{{p['device']}}" data-obj="{{p['obj']}}" data-b="{{hostname}}" onclick="toggleRowSelection(this)" style="cursor: pointer;">
                <td class="text-primary" style="font-weight: 600;">{{p['protocol']}}</td>
                <td>
                    <div style="display: flex; align-items: center; justify-content: space-between; gap: 10px;">
                        <span>
                            % if p['protocol'].lower() == 'bacnet' and str(p['device']) in bacnet_aliases:
                                <span title="Device ID: {{p['device']}}" style="cursor: help; color: var(--tertiary); font-weight: bold; border-bottom: 1px dotted var(--tertiary);">
                                    {{bacnet_aliases[str(p['device'])]}}
                                </span>
                            % else:
                                {{p['device']}}
                            % end
                        </span>
                        <button type="button"
                                title="Purger les relevés de l'équipement {{p['device']}}"
                                data-chantier-id="{{chantier['id']}}"
                                data-hostname="{{hostname}}"
                                data-protocol="{{p['protocol']}}"
                                data-device="{{p['device']}}"
                                onclick="event.stopPropagation(); purgeDeviceFromButton(this);"
                                class="btn-icon btn-icon-danger"
                                style="width: 24px; height: 24px; opacity: 0.4;">
                            <span class="material-symbols-outlined" style="font-size: 14px;">delete</span>
                        </button>
                    </div>
                </td>
                <td class="font-mono text-muted" style="font-size: 0.8rem;">{{p['obj']}}</td>
                <td class="point-label">{{p['label'] or '—'}}</td>
                <td style="text-align: right; font-weight: 700;">
                    <div style="display: flex; align-items: center; justify-content: flex-end; gap: 8px;">
                        <span class="trend-indicator" data-b="{{hostname}}" data-p="{{p['protocol']}}" data-d="{{p['device']}}" data-o="{{p['obj']}}">
                            % if p['trend_dir'] == 'up':
                                <span class="text-secondary">▲</span>
                            % elif p['trend_dir'] == 'down':
                                <span class="text-danger">▼</span>
                            % elif p['trend_dir'] == 'stable':
                                <span class="text-muted">=</span>
                            % elif p['trend_dir'] == 'diff':
                                <span class="text-tertiary">🔄</span>
                            % end
                        </span>
                        <span class="trend-val-val font-mono"
                              data-b="{{hostname}}"
                              data-p="{{p['protocol']}}"
                              data-d="{{p['device']}}"
                              data-o="{{p['obj']}}"
                              data-raw-val="{{p['last_value'] if p['last_value'] is not None else ''}}"
                              style="font-size: 0.95rem;">
                            {{p['last_value'] if p['last_value'] is not None else '—'}}
                        </span>
                    </div>
                </td>
                <td style="text-align: center;">
                    <span class="trend-count-val font-mono"
                          data-b="{{hostname}}"
                          data-p="{{p['protocol']}}"
                          data-d="{{p['device']}}"
                          data-o="{{p['obj']}}"
                          style="{{'color: var(--primary); font-weight: bold;' if p['trend_count'] > 0 else 'color: var(--outline); font-size: 0.85em;'}}">
                        {{p['trend_count']}}
                    </span>
                </td>
                <td style="text-align: center;">
                    <span class="update-indicator" 
                          data-b="{{hostname}}"
                          data-p="{{p['protocol']}}"
                          data-d="{{p['device']}}"
                          data-o="{{p['obj']}}"
                          style="opacity: 0; color: var(--secondary); font-size: 1.5rem; line-height: 0;">
                        ●
                    </span>
                </td>
            </tr>
            % end
        </tbody>
    </table>
</div>
