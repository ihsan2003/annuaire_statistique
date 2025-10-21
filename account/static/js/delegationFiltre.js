document.addEventListener('DOMContentLoaded', function () {
    const regionSelect = document.getElementById('region-select');
    const delegationSelect = document.getElementById('delegation-select');

    regionSelect.addEventListener('change', function () {
        const regionId = this.value;

        // Réinitialiser le champ des délégations
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
                .catch(error => {
                    console.error('Erreur lors du chargement des délégations :', error);
                    alert('Erreur lors du chargement des délégations. Consultez la console.');
                });

        }
    });
});
