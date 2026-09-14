% if not boitiers:
    <div class="card luminescent-border">
        <div style="display: flex; align-items: center; gap: 15px; color: var(--outline);">
            <span class="material-symbols-outlined" style="font-size: 32px;">info</span>
            <p style="margin: 0;">Aucun boîtier n'est actuellement assigné à ce chantier.</p>
        </div>
    </div>
% else:
    % for hostname, data in boitiers.items():
        <div class="card">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; border-bottom: 1px solid var(--outline-variant); padding-bottom: 12px;">
                <h3 style="margin: 0; display: flex; align-items: center; gap: 10px;">
                    <span class="material-symbols-outlined text-primary">developer_board</span>
                    Boîtier : <span class="text-primary font-mono">{{hostname}}</span>
                </h3>
                % if data['tailscale_name']:
                    <div class="user-badge" style="background: rgba(74, 225, 118, 0.05); border-color: var(--secondary);">
                        <span class="material-symbols-outlined icon-sm text-secondary">vpn_lock</span>
                        <span class="text-secondary" style="font-size: 0.75rem; font-weight: 700; font-family: var(--font-mono);">{{data['tailscale_name']}}</span>
                    </div>
                % end
            </div>

            % if not data['points']:
                <p class="hint">Aucun point configuré pour ce boîtier.</p>
            % else:
                % include('points_table.tpl', hostname=hostname, points=data['points'], bacnet_aliases=bacnet_aliases, chantier=chantier)
            % end
        </div>
    % end

    % include('points_scripts.tpl', BASE_PATH=BASE_PATH)
    <script>startRealtimeCounts({{chantier['id']}});</script>
% end
