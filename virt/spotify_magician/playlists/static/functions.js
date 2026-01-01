const mobilemenuclosed = document.querySelector('#mobilemenuclosed');
const mobilemenuopened = document.querySelector('#mobilemenuopened');
const mobilemenu = document.querySelector('#mobilemenu');
const button = document.querySelector('#button');

function menubutton() {
    if (mobilemenu.classList.contains('hidden')) {
        mobilemenu.classList.remove('hidden');
        mobilemenuopened.classList.remove('hidden');
        mobilemenuclosed.classList.add('hidden');
    } else {
        mobilemenu.classList.add('hidden');
        mobilemenuopened.classList.add('hidden');
        mobilemenuclosed.classList.remove('hidden');
    }
    }
