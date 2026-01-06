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
