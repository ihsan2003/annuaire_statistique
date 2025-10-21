document.addEventListener('DOMContentLoaded', () => {
    const regionSelect = document.getElementById('region-select');
    const delegationSelect = document.getElementById('delegation-select');

    if (regionSelect && delegationSelect) {
        regionSelect.addEventListener('change', () => {
            const regionId = regionSelect.value;
            delegationSelect.innerHTML = '<option value="">-- Délégation --</option>';
            delegationSelect.disabled = true;

            if (regionId) {
                fetch(`/ajax/get-delegations/?region_id=${regionId}`)
                    .then(response => response.json())
                    .then(data => {
                        data.delegations.forEach(deleg => {
                            const option = document.createElement('option');
                            option.value = deleg.id_delegation;
                            option.textContent = deleg.delegation;
                            delegationSelect.appendChild(option);
                        });
                        delegationSelect.disabled = false;
                    })
                    .catch(err => {
                        console.error('Erreur chargement des délégations', err);
                    });
            }
        });
    }
});
