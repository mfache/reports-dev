% rebase('layout.tpl', title='Nodes - Delta Thermic')
<div class="container">
    <h1 style="color: var(--text-main); font-size: 1.8em; margin-top: 20px; margin-bottom: 10px;">Nodes - Liste des boîtiers</h1>
    <p style="color: var(--text-muted); margin-bottom: 20px;">Aperçu de l'état de la flotte et des présences.</p>

    % include('nodes_table.tpl', boitiers=boitiers, trends_count=trends_count, config_count=config_count, format_human_date=format_human_date)
</div>
