(function() {
    'use strict';

    function togglePriceTier() {
        var reasonField = document.getElementById('id_reason');
        var priceTierRow = document.querySelector('.field-price_tier');
        if (!reasonField || !priceTierRow) return;

        var priceTierField = document.getElementById('id_price_tier');
        if (reasonField.value === 'sale') {
            priceTierRow.style.display = '';
            if (priceTierField && !priceTierField.value) {
                priceTierField.value = 'sp1';
            }
        } else {
            priceTierRow.style.display = 'none';
            if (priceTierField) priceTierField.value = '';
        }
    }

    document.addEventListener('DOMContentLoaded', function() {
        togglePriceTier();
        var reasonField = document.getElementById('id_reason');
        if (reasonField) {
            reasonField.addEventListener('change', togglePriceTier);
        }
    });
})();
