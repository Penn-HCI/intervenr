// My Data JS: Runs through all of the different components.
"use strict";


function clickContactEmailFormBtn(e) {
    let btn = e.composedPath()[0];
    let contactForm = document.querySelector('#contact_email_form');
    if (contactForm.classList.contains('hidden-slide')) {
        btn.innerText = 'Submit New Email';
        contactForm.classList.toggle('hidden-slide');
        contactForm.classList.toggle('show-slide');
    }
    else {
        contactForm.submit();
    }
}

function yesConfirm(e) {
    let elem = e.composedPath()[2].querySelector('.main__data--label-modify img');
    let src_page_url = elem.getAttribute('src_page_url');
    let created_time__date = elem.getAttribute('created_time__date');
    created_time__date = new Date(created_time__date).toLocaleDateString('fr-CA');
    let created_time__hour = elem.getAttribute('created_time__hour');
    let created_time__minute = elem.getAttribute('created_time__minute');
    let urlForm = document.querySelector('#url_form');
    let urlFormDataElem = urlForm.querySelector('#id_redaction_list');
    let urlParams = new URLSearchParams(window.location.search);
    let pg = 0;
    if (urlParams.has('pg')) {
        pg = Number(urlParams.get('pg'));
    }
    let dataJson = {urlRecords: [], pg: pg};
    if (urlFormDataElem.value != 'null') {
        dataJson = JSON.parse(urlFormDataElem.value);
    }
    dataJson.urlRecords.push({
        "src_page_url": src_page_url,
        "created_time__date": created_time__date,
        "created_time__hour": created_time__hour,
        "created_time__minute": created_time__minute,
    });
    urlFormDataElem.value = JSON.stringify(dataJson);
    urlForm.submit();
}

function noConfirm(e) {
    let delIcon = e.composedPath()[2].querySelector('.main__data--label-modify img');
    delIcon.classList.toggle('ico');
    delIcon.classList.toggle('ico--click');
    let elem = e.composedPath()[1];
    elem.remove();
    console.log(e);
}

function runDel(e) {
    let elem = e.composedPath()[0];
    elem.classList.toggle('ico');
    elem.classList.toggle('ico--click');
    
    let confirmDelTxt = document.createElement('div');
    confirmDelTxt.className = 'modify-confirm-txt';
    confirmDelTxt.innerText = 'Are you sure you want to delete this record?';
    
    let confirmDelYesBtn = document.createElement('div');
    confirmDelYesBtn.className = 'modify-confirm-btn btn-red';
    confirmDelYesBtn.innerText = 'Yes';
    confirmDelYesBtn.addEventListener('click', yesConfirm);

    let confirmDelNoBtn = document.createElement('div');
    confirmDelNoBtn.className = 'modify-confirm-btn btn-blue';
    confirmDelNoBtn.innerText = 'No';
    confirmDelNoBtn.addEventListener('click', noConfirm);

    let confirmDel = document.createElement('div');
    confirmDel.className ='modify-confirm';
    confirmDel.append(confirmDelTxt, confirmDelYesBtn, confirmDelNoBtn);
    elem.parentElement.parentElement.append(confirmDel);
}

function runPlus(e) {
    let elem = e.composedPath()[0];
    elem.classList.toggle('ico');
    elem.classList.toggle('ico--click');
    elem.previousElementSibling.classList.toggle('clip-url');
    elem.previousElementSibling.classList.toggle('unclip-url');
}

window.addEventListener('load', () => {
    let delIcons = document.querySelectorAll('.main__data--label-modify img.ico');
    for (let delIco of delIcons) {
        delIco.addEventListener('click', runDel);
    }
    let plusIcons = document.querySelectorAll('img.main__data--label-expand');
    for (let plusIco of plusIcons) {
        plusIco.addEventListener('click', runPlus);
    }
    let contactEmailFormBtn = document.querySelector('#contact_email_form_submit');
    contactEmailFormBtn.addEventListener('click', clickContactEmailFormBtn);
});

