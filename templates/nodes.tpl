% # Page Nodes "Poupée Moyenne" (Kinetic Infrastructure)
<div class="header-with-actions">
    <div>
        <h2>🛰️ État de la Flotte (Nodes)</h2>
        <p class="hint">Surveillance de l'état de connexion et de synchronisation des boîtiers rpinode.</p>
    </div>
</div>

<div class="stats-banner">
    <div class="stat-item">
        <div class="stat-val">{{len(boitiers)}}</div>
        <div class="stat-lbl">Boîtiers</div>
    </div>
    <div class="stat-divider"></div>
    <div class="stat-item">
        <div class="stat-val text-secondary">{{len([b for b in boitiers if b['last_sync_at'] and (datetime.datetime.now() - b['last_sync_at']).total_seconds() < 900])}}</div>
        <div class="stat-lbl">En Ligne</div>
    </div>
    <div class="stat-divider"></div>
    <div class="stat-item">
        <div class="stat-val text-primary">{{sum(trends_count.values())}}</div>
        <div class="stat-lbl">Total Relevés</div>
    </div>
</div>

% include('nodes_table.tpl', boitiers=boitiers, trends_count=trends_count, config_count=config_count, format_human_date=format_human_date)
