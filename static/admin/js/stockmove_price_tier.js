(function() {
    'use strict';

    function togglePriceTier() {
        var reasonField = document.getElementById('id_reason');
        var priceTierRow = document.querySelector('.field-price_tier');
        if (!reasonField || !priceTierRow) return;

        if (reasonField.value === 'sale') {
            priceTierRow.style.display = '';
        } else {
            priceTierRow.style.display = 'none';
            // Clear the value when hidden
            var priceTierField = document.getElementById('id_price_tier');
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
