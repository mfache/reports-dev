<div class="header-with-actions">
    <div>
        <h2>🏗️ Gestion des Chantiers</h2>
        <p class="hint">Créer, modifier ou archiver des chantiers et attribuer leurs chargés d'affaires.</p>
    </div>
    <button class="btn-primary" onclick="openModal('modal-add-chantier')">
        <span class="material-symbols-outlined icon-sm">add</span> Ajouter un chantier
    </button>
</div>

<div class="card" style="margin-bottom: 30px;">
    <h3>Chantiers Actifs</h3>
    <div class="table-scroll">
        <table class="data-table">
            <thead>
                <tr>
                    <th>Réf.</th>
                    <th>Adresse</th>
                    <th>Géolocalisation</th>
                    <th>Chargé d'affaires</th>
                    <th>Actions</th>
                </tr>
            </thead>
            <tbody>
                % for c in chantiers:
                <tr>
                    <td class="font-mono text-primary font-bold">
                        <a href="{{BASE_PATH}}/chantier/{{c['id']}}" style="color:var(--primary); text-decoration:none;">{{c['ref']}}</a>
                    </td>
                    <td>{{c['adresse'] or '—'}}</td>
                    <td><span class="font-mono text-muted" style="font-size:0.85rem;">{{c['geolocalisation'] or '—'}}</span></td>
                    <td>
                        % if c['charge_affaires']:
                            <span class="badge" style="background: rgba(76, 215, 246, 0.15); color: var(--primary);">{{c['charge_affaires']}}</span>
                        % else:
                            <span class="text-muted">— Non attribué —</span>
                        % end
                    </td>
                    <td>
                        <div style="display: flex; gap: 5px; align-items: center;">
                            <button class="btn-secondary" onclick="editChantier({{c['id']}}, '{{c['ref']}}', '{{(c['adresse'] or '').replace('\'', '\\\'')}}', '{{(c['geolocalisation'] or '').replace('\'', '\\\'')}}', {{c['utilisateurs_id'] or 'null'}})">Modifier</button>
                            <a href="{{BASE_PATH}}/chantier/{{c['id']}}" class="btn-secondary">Voir</a>
                        </div>
                    </td>
                </tr>
                % end
                % if not chantiers:
                <tr><td colspan="5" class="text-muted" style="text-align:center;">Aucun chantier actif.</td></tr>
                % end
            </tbody>
        </table>
    </div>
</div>

% if archived_chantiers:
<div class="card" style="opacity: 0.85;">
    <h3>Chantiers Archivés</h3>
    <div class="table-scroll">
        <table class="data-table">
            <thead>
                <tr>
                    <th>Réf.</th>
                    <th>Adresse</th>
                    <th>Chargé d'affaires</th>
                    <th>Actions</th>
                </tr>
            </thead>
            <tbody>
                % for c in archived_chantiers:
                <tr>
                    <td class="font-mono text-muted">{{c['ref']}}</td>
                    <td class="text-muted">{{c['adresse'] or '—'}}</td>
                    <td class="text-muted">{{c['charge_affaires'] or '—'}}</td>
                    <td>
                        <form action="{{BASE_PATH}}/admin/chantiers/{{c['id']}}/unarchive" method="POST" style="display:inline;" hx-boost="false">
                            <button type="submit" class="btn-secondary">Restaurer</button>
                        </form>
                    </td>
                </tr>
                % end
            </tbody>
        </table>
    </div>
</div>
% end

<!-- Modal Ajouter -->
<div id="modal-add-chantier" class="modal">
    <div class="modal-content" style="max-width: 550px;">
        <h3>Ajouter un chantier</h3>
        <form action="{{BASE_PATH}}/admin/chantiers/create" method="POST" hx-boost="false">
            <div class="form-group">
                <label>Référence du chantier</label>
                <input type="text" name="ref" class="input-dark" placeholder="Ex: EPHEC, POSTE..." required>
            </div>
            <div class="form-group">
                <label>Adresse</label>
                <input type="text" id="add-adresse" name="adresse" class="input-dark" placeholder="Ex: Avenue du Port, 1000 Bruxelles">
            </div>
            <div class="form-group">
                <label>Géolocalisation (lat, lon)</label>
                <div style="display: flex; gap: 8px;">
                    <input type="text" id="add-geolocalisation" name="geolocalisation" class="input-dark" placeholder="Ex: 50.8503, 4.3517" style="flex: 1;">
                    <button type="button" class="btn-secondary" onclick="openMapPicker('add-geolocalisation', 'add-adresse')" title="Sélectionner sur la carte">
                        <span class="material-symbols-outlined icon-sm">map</span>
                    </button>
                    <button type="button" class="btn-secondary" onclick="getCurrentLocation('add-geolocalisation')" title="Ma position GPS actuelle">
                        <span class="material-symbols-outlined icon-sm">my_location</span>
                    </button>
                </div>
            </div>
            <div class="form-group">
                <label>Chargé d'affaires</label>
                <select name="utilisateurs_id" class="input-dark">
                    <option value="">-- Non attribué --</option>
                    % for u in users:
                    <option value="{{u['id']}}">{{u['nom'] or u['ref']}}</option>
                    % end
                </select>
            </div>
            <div style="display: flex; justify-content: flex-end; gap: 10px; margin-top: 20px;">
                <button type="button" class="btn-secondary" onclick="closeModal('modal-add-chantier')">Annuler</button>
                <button type="submit" class="btn-primary">Ajouter</button>
            </div>
        </form>
    </div>
</div>

<!-- Modal Modifier -->
<div id="modal-edit-chantier" class="modal">
    <div class="modal-content" style="max-width: 550px;">
        <h3>Modifier le chantier</h3>
        <form id="form-edit-chantier" method="POST" hx-boost="false">
            <div class="form-group">
                <label>Référence</label>
                <input type="text" id="edit-ref" name="ref" class="input-dark" required>
            </div>
            <div class="form-group">
                <label>Adresse</label>
                <input type="text" id="edit-adresse" name="adresse" class="input-dark">
            </div>
            <div class="form-group">
                <label>Géolocalisation (lat, lon)</label>
                <div style="display: flex; gap: 8px;">
                    <input type="text" id="edit-geolocalisation" name="geolocalisation" class="input-dark" style="flex: 1;">
                    <button type="button" class="btn-secondary" onclick="openMapPicker('edit-geolocalisation', 'edit-adresse')" title="Sélectionner sur la carte">
                        <span class="material-symbols-outlined icon-sm">map</span>
                    </button>
                    <button type="button" class="btn-secondary" onclick="getCurrentLocation('edit-geolocalisation')" title="Ma position GPS actuelle">
                        <span class="material-symbols-outlined icon-sm">my_location</span>
                    </button>
                </div>
            </div>
            <div class="form-group">
                <label>Chargé d'affaires</label>
                <select id="edit-utilisateurs-id" name="utilisateurs_id" class="input-dark">
                    <option value="">-- Non attribué --</option>
                    % for u in users:
                    <option value="{{u['id']}}">{{u['nom'] or u['ref']}}</option>
                    % end
                </select>
            </div>
            <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 20px;">
                <button type="button" class="btn-secondary" style="border-color: var(--error); color: var(--error);" onclick="document.getElementById('form-archive-chantier').submit();">Archiver</button>
                <div style="display: flex; gap: 10px;">
                    <button type="button" class="btn-secondary" onclick="closeModal('modal-edit-chantier')">Annuler</button>
                    <button type="submit" class="btn-primary">Enregistrer</button>
                </div>
            </div>
        </form>
        <form id="form-archive-chantier" method="POST" style="display:none;" hx-boost="false"></form>
    </div>
</div>

<!-- Modal Map Picker (Carte OpenStreetMap / Leaflet) -->
<div id="modal-map-picker" class="modal" style="z-index: 1100;">
    <div class="modal-content" style="max-width: 700px; width: 90%;">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px;">
            <h3 style="margin: 0;">🗺️ Sélectionner la position sur la carte</h3>
            <button type="button" class="btn-secondary" onclick="closeModal('modal-map-picker')">✕</button>
        </div>
        <p class="hint" style="margin-bottom: 10px;">Cliquez sur la carte ou déplacez le marqueur pour définir les coordonnées GPS.</p>
        <div id="map-picker-container" style="height: 380px; width: 100%; border-radius: var(--radius-md); border: 1px solid var(--outline); background: var(--surface-low);"></div>
        <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 15px; flex-wrap: wrap; gap: 10px;">
            <span id="map-picker-coords" class="font-mono text-primary" style="font-weight: 600;">—</span>
            <div style="display: flex; gap: 10px;">
                <button type="button" class="btn-secondary" onclick="closeModal('modal-map-picker')">Annuler</button>
                <button type="button" class="btn-primary" onclick="confirmMapPicker()">Valider la position</button>
            </div>
        </div>
    </div>
</div>

<style>
.modal { display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.5); z-index: 1000; align-items: center; justify-content: center; }
.modal-content { background: var(--surface); padding: 25px; border-radius: var(--radius-lg); border: 1px solid var(--outline); width: 100%; }
</style>

<script>
function openModal(id) { document.getElementById(id).style.display = 'flex'; }
function closeModal(id) { document.getElementById(id).style.display = 'none'; }
function editChantier(id, ref, adresse, geolocalisation, utilisateurs_id) {
    document.getElementById('form-edit-chantier').action = '{{BASE_PATH}}/admin/chantiers/' + id + '/update';
    document.getElementById('form-archive-chantier').action = '{{BASE_PATH}}/admin/chantiers/' + id + '/archive';
    document.getElementById('edit-ref').value = ref;
    document.getElementById('edit-adresse').value = adresse;
    document.getElementById('edit-geolocalisation').value = geolocalisation;
    document.getElementById('edit-utilisateurs-id').value = utilisateurs_id ? utilisateurs_id : '';
    openModal('modal-edit-chantier');
}

let pickerMap = null;
let pickerMarker = null;
let activeGeoInputId = null;
let activeAddressInputId = null;
let selectedLat = null;
let selectedLng = null;

function loadLeaflet(callback) {
    if (window.L) {
        callback();
        return;
    }
    const css = document.createElement('link');
    css.rel = 'stylesheet';
    css.href = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.css';
    document.head.appendChild(css);

    const script = document.createElement('script');
    script.src = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.js';
    script.onload = callback;
    document.head.appendChild(script);
}

function getCurrentLocation(inputId) {
    if (!navigator.geolocation) {
        alert("La géolocalisation n'est pas supportée par votre navigateur.");
        return;
    }
    navigator.geolocation.getCurrentPosition(
        (pos) => {
            const lat = pos.coords.latitude.toFixed(6);
            const lng = pos.coords.longitude.toFixed(6);
            document.getElementById(inputId).value = `${lat}, ${lng}`;
        },
        (err) => {
            alert(`Erreur de géolocalisation : ${err.message}`);
        },
        { enableHighAccuracy: true, timeout: 10000 }
    );
}

function openMapPicker(inputId, addressInputId) {
    activeGeoInputId = inputId;
    activeAddressInputId = addressInputId;
    openModal('modal-map-picker');

    loadLeaflet(() => {
        setTimeout(initOrUpdateMapPicker, 100);
    });
}

function initOrUpdateMapPicker() {
    let lat = 50.8503;
    let lng = 4.3517;
    let zoom = 8;

    const val = document.getElementById(activeGeoInputId).value.trim();
    if (val && val.includes(',')) {
        const parts = val.split(',').map(p => parseFloat(p.trim()));
        if (parts.length === 2 && !isNaN(parts[0]) && !isNaN(parts[1])) {
            lat = parts[0];
            lng = parts[1];
            zoom = 15;
        }
    }

    selectedLat = lat;
    selectedLng = lng;

    if (!pickerMap) {
        pickerMap = L.map('map-picker-container').setView([lat, lng], zoom);
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            maxZoom: 19,
            attribution: '© OpenStreetMap'
        }).addTo(pickerMap);

        pickerMarker = L.marker([lat, lng], { draggable: true }).addTo(pickerMap);

        pickerMap.on('click', (e) => {
            selectedLat = e.latlng.lat;
            selectedLng = e.latlng.lng;
            pickerMarker.setLatLng([selectedLat, selectedLng]);
            updateCoordsLabel();
        });

        pickerMarker.on('dragend', (e) => {
            const pos = pickerMarker.getLatLng();
            selectedLat = pos.lat;
            selectedLng = pos.lng;
            updateCoordsLabel();
        });
    } else {
        pickerMap.invalidateSize();
        pickerMap.setView([lat, lng], zoom);
        pickerMarker.setLatLng([lat, lng]);
    }
    updateCoordsLabel();
}

function updateCoordsLabel() {
    if (selectedLat && selectedLng) {
        document.getElementById('map-picker-coords').textContent = `${selectedLat.toFixed(6)}, ${selectedLng.toFixed(6)}`;
    }
}

function confirmMapPicker() {
    if (activeGeoInputId && selectedLat && selectedLng) {
        const coordsStr = `${selectedLat.toFixed(6)}, ${selectedLng.toFixed(6)}`;
        document.getElementById(activeGeoInputId).value = coordsStr;

        const addrInput = document.getElementById(activeAddressInputId);
        if (addrInput && !addrInput.value.trim()) {
            fetch(`https://nominatim.openstreetmap.org/reverse?format=json&lat=${selectedLat}&lon=${selectedLng}`)
                .then(r => r.json())
                .then(data => {
                    if (data && data.display_name) {
                        addrInput.value = data.display_name;
                    }
                })
                .catch(() => {});
        }
    }
    closeModal('modal-map-picker');
}
</script>
