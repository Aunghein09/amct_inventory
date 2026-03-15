(function() {
    'use strict';

    function toggleCustomSize() {
        var sizeField = document.getElementById('id_size');
        var customRow = document.querySelector('.field-custom_size');
        if (!sizeField || !customRow) return;

        if (sizeField.value === 'custom') {
            customRow.style.display = '';
        } else {
            customRow.style.display = 'none';
        }
    }

    document.addEventListener('DOMContentLoaded', function() {
        toggleCustomSize();
        var sizeField = document.getElementById('id_size');
        if (sizeField) {
            sizeField.addEventListener('change', toggleCustomSize);
        }
    });
})();
