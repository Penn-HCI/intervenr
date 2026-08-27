// Simple Admin: JavaScript for running the simple admin.
"use strict";


// Plus Button Listener
function expandBtnClickListener(e) {
    let btn = e.composedPath()[0];
    btn.classList.toggle('ico');
    btn.classList.toggle('ico--click');
    let clippedBtns = e.composedPath()[2].querySelectorAll('.clip,.unclip');
    for (let clippedBtn of clippedBtns) {
        clippedBtn.classList.toggle('clip');
        clippedBtn.classList.toggle('unclip');
    }
}


// File Upload Listener
function fileUploadListener(e) {
    let input = e.target;
    input.parentElement.parentElement.submit();
}


// Mass Action Submit Listener
function massActionSubmitListener(e) {
    let btn = e.composedPath()[0];
    let selectValue = btn.previousElementSibling.value;
    if (selectValue != "") {
        let dataElem = e.composedPath()[3];
        let json_payload = {action_data: dataElem.id, selected_action: selectValue, records: []};
        let dataRows = dataElem.querySelectorAll('.main__data--row .main__data--col input[type=checkbox]');
        for (let checkbox of dataRows) {
            if (checkbox.checked && checkbox.hasAttribute('recordId')) {
                json_payload.records.push(checkbox.getAttribute('recordId'));
            }
        }
        let form = document.querySelector('#form-json-data-submit');
        let jsonInput = document.querySelector('#form-json-data-submit #id_json_data');
        jsonInput.value = JSON.stringify(json_payload);
        form.submit();
    }
}


// Select All
function selectBtnListener(e) {
    let data = e.composedPath()[3];
    let inputBtns = data.querySelectorAll('input[type=checkbox]');
    for (let input of inputBtns) {
        if (input.checked) {
            input.checked = false;
        }
        else {
            input.checked = true;
        }
    }
}

// Ad Swap Pairs
function adSwapBtnListener(e) {
    let input = e.target;
    input.parentElement.submit();
}


// Register all the event listener components
window.addEventListener('load', (e) => {
    // Attach listeners to the expand icons
    let plusIcons = document.querySelectorAll('img.exp-btn');
    for (let plusBtn of plusIcons) {
        plusBtn.addEventListener('click', expandBtnClickListener);
    }
    
    // Attach a submit for the forms on each file input label
    let actionGridFileForms = document.querySelectorAll('.main__action-grid--file-input');
    for (let inputBtn of actionGridFileForms) {
        inputBtn.addEventListener('input', fileUploadListener);
    }

    // Attach a listener to each of the mass action sections of the data
    let actionDropdownSubmitBtns = document.querySelectorAll('.main__data--mass-action-submit');
    for (let submitBtn of actionDropdownSubmitBtns) {
        submitBtn.addEventListener('click', massActionSubmitListener);
    }

    // Attach a listener for the select button
    let selectBtns = document.querySelectorAll('.select');
    for (let selectBtn of selectBtns) {
        selectBtn.addEventListener('click', selectBtnListener);
    }

    // Attach custom listener for Assign Ad Swap Pairs button
    let adSwapBtn = document.getElementById("quick-assign-pairs");
    adSwapBtn.addEventListener("click", adSwapBtnListener);
});