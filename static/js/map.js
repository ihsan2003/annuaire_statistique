// Récupérer les URLs depuis les attributs data
const mapElement = document.getElementById('map');
const regionGeojsonUrl = mapElement.dataset.regionGeojson;
const delegationGeojsonUrl = mapElement.dataset.delegationGeojson;
const centresApiUrl = mapElement.dataset.centresApi;

let map = L.map('map', {
    zoomControl: true,
    preferCanvas: false
}).setView([31.7917, -7.0926], 6);

L.tileLayer('https://{s}.tile.openstreetmap.fr/hot/{z}/{x}/{y}.png', {
    maxZoom: 18,
    attribution: '© OpenStreetMap contributors, HOT'
}).addTo(map);

const regionStyle = {
    color: "#8B5CF6",
    weight: 3,
    fillColor: "#A78BFA",
    fillOpacity: 0.3
};

const delegationStyle = {
    color: "#F97316",
    weight: 2,
    fillColor: "#FCA5A5",
    fillOpacity: 0.1
};

let delegationLayer = null;
let centreMarkers = [];
let regionLayer = null;
window.regionLabels = [];
window.delegationLabels = [];

// État de navigation
let currentView = 'regions';
let currentRegion = null;
let currentDelegation = null;

// Créer le contrôle personnalisé de retour
L.Control.BackButton = L.Control.extend({
    onAdd: function(map) {
        const container = L.DomUtil.create('div', 'leaflet-bar leaflet-control leaflet-control-back');
        container.innerHTML = '<i class="fa-solid fa-arrow-left"></i> Retour';
        container.title = 'Retour à la couche précédente';
        
        // Empêcher la propagation des clics à la carte
        L.DomEvent.disableClickPropagation(container);
        L.DomEvent.on(container, 'click', handleBackClick);
        
        return container;
    },
    
    onRemove: function(map) {
        // Nettoyage si nécessaire
    }
});

// Ajouter le contrôle à la carte (position topright)
const backControl = new L.Control.BackButton({ position: 'topright' });
backControl.addTo(map);

// Récupérer l'élément DOM du bouton
const backButton = document.querySelector('.leaflet-control-back');

function handleBackClick(e) {
    e.stopPropagation();
    
    if (currentView === 'centres') {
        loadDelegations(currentRegion);
        currentView = 'delegations';
        currentDelegation = null;
    } else if (currentView === 'delegations') {
        resetToRegions();
    }
    updateBackButton();
}

function updateBackButton() {
    if (currentView === 'regions') {
        backButton.classList.remove('visible');
    } else {
        backButton.classList.add('visible');
    }
}

function resetToRegions() {
    if (delegationLayer) {
        map.removeLayer(delegationLayer);
        delegationLayer = null;
    }
    
    centreMarkers.forEach(m => map.removeLayer(m));
    centreMarkers = [];
    
    window.delegationLabels.forEach(l => map.removeLayer(l));
    window.delegationLabels = [];
    
    if (regionLayer) {
        regionLayer.addTo(map);
    }
    window.regionLabels.forEach(l => l.addTo(map));
    
    map.setView([31.7917, -7.0926], 6);
    currentView = 'regions';
    currentRegion = null;
    currentDelegation = null;
}

// Fetch regions
fetch(regionGeojsonUrl)
    .then(res => res.json())
    .then(data => {
        console.log("=== DIAGNOSTIC REGIONS ===");
        console.log("Nombre de features:", data.features.length);
        if (data.features.length > 0) {
            console.log("Type de géométrie:", data.features[0].geometry.type);
            console.log("Première feature:", data.features[0]);
        }
        
        regionLayer = L.geoJSON(data, {
            style: regionStyle,
            onEachFeature: (feature, layer) => {
                console.log(`Region: ${feature.properties.region}, Type: ${feature.geometry.type}`);
                
                const regionNom = feature.properties.region;
                const center = layer.getBounds().getCenter();

                const label = L.marker(center, {
                    icon: L.divIcon({
                        className: 'region-label',
                        html: regionNom,
                        iconSize: [100, 20],
                        iconAnchor: [50, 10]
                    })
                }).addTo(map);
                window.regionLabels.push(label);

                layer.on('click', () => {
                    map.fitBounds(layer.getBounds());
                    window.regionLabels.forEach(l => map.removeLayer(l));
                    map.removeLayer(regionLayer);
                    currentRegion = regionNom;
                    loadDelegations(regionNom);
                });

                layer.on('mouseover', () => layer.setStyle({ fillOpacity: 0.4 }));
                layer.on('mouseout', () => layer.setStyle({ fillOpacity: 0.3 }));
            }
        }).addTo(map);
        
        updateBackButton();
    });

function loadDelegations(regionNom) {
    if (delegationLayer) map.removeLayer(delegationLayer);
    centreMarkers.forEach(m => map.removeLayer(m));
    centreMarkers = [];

    window.delegationLabels.forEach(l => map.removeLayer(l));
    window.delegationLabels = [];

    fetch(delegationGeojsonUrl)
        .then(res => res.json())
        .then(data => {
            const filtered = {
                ...data,
                features: data.features.filter(f => f.properties.region === regionNom)
            };

            delegationLayer = L.geoJSON(filtered, {
                style: delegationStyle,
                onEachFeature: (feature, layer) => {
                    const delNom = feature.properties.delegation;

                    layer.on('click', () => {
                        map.fitBounds(layer.getBounds());
                        currentDelegation = delNom;
                        loadCentres(delNom);
                    });

                    const center = layer.getBounds().getCenter();
                    const label = L.marker(center, {
                        icon: L.divIcon({
                            className: 'delegation-label',
                            html: delNom,
                            iconSize: [100, 20],
                            iconAnchor: [50, 10]
                        })
                    }).addTo(map);
                    window.delegationLabels.push(label);

                    layer.on('mouseover', () => layer.setStyle({ fillOpacity: 0.5 }));
                    layer.on('mouseout', () => layer.setStyle({ fillOpacity: 0.4 }));
                }
            }).addTo(map);
            
            currentView = 'delegations';
            updateBackButton();
        });
}

// Charger les programmes pour le filtre
fetch(centresApiUrl)
    .then(res => res.json())
    .then(data => {
        const programmes = [...new Set(data.map(c => c.programme_updated))].filter(Boolean);
        const select = document.getElementById('programmeFilter');
        programmes.forEach(p => {
            const option = document.createElement('option');
            option.value = p;
            option.textContent = p;
            select.appendChild(option);
        });
    });

function loadCentres(delegationNom) {
    centreMarkers.forEach(m => map.removeLayer(m));
    centreMarkers = [];

    fetch(`${centresApiUrl}?delegation=${encodeURIComponent(delegationNom)}`)
        .then(res => {
            if (!res.ok) {
                throw new Error(`Erreur HTTP! Statut: ${res.status}`);
            }
            return res.json();
        })
        .then(data => {
            data.forEach(c => {
                const marker = L.marker([c.latitude, c.longitude], {
                    icon: L.icon({
                        iconUrl: 'https://cdn-icons-png.flaticon.com/512/484/484167.png',
                        iconSize: [25, 25],
                        iconAnchor: [12, 24],
                        popupAnchor: [0, -20]
                    })
                }).bindPopup(`<strong>Centre :</strong> ${c.nom}<br><strong>Axe :</strong> ${c.axe_updated}<br><strong>Programme :</strong> ${c.programme_updated}<br><strong>Nombre Bénéficiaires :</strong> ${c.nb_beneficiaires_t}`);
                marker.addTo(map);
                centreMarkers.push(marker);
            });
            
            currentView = 'centres';
            updateBackButton();
        })
        .catch(error => {
            console.error("Erreur lors du chargement des centres :", error);
        });
}