/* OpsPortal - shared front-end behaviour for the server-rendered pages.
   Theme toggle carried over from the AssetFlow reference design system,
   plus the avatar cropper used by the signup / profile screens. */

document.addEventListener('DOMContentLoaded', () => {
    const themeToggleBtn = document.getElementById('theme-toggle-btn');
    const htmlElement = document.documentElement;

    // SVG Icons for Light and Dark modes
    const sunIcon = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><path d="M12 7c-2.76 0-5 2.24-5 5s2.24 5 5 5 5-2.24 5-5-2.24-5-5-5zM2 13h2c.55 0 1-.45 1-1s-.45-1-1-1H2c-.55 0-1 .45-1 1s.45 1 1 1zm18 0h2c.55 0 1-.45 1-1s-.45-1-1-1h-2c-.55 0-1 .45-1 1s.45 1 1 1zM11 2v2c0 .55.45 1 1 1s1-.45 1-1V2c0-.55-.45-1-1-1s-1 .45-1 1zm0 18v2c0 .55.45 1 1 1s1-.45 1-1v-2c0-.55-.45-1-1-1s-1 .45-1 1zM5.99 4.58c-.39-.39-1.03-.39-1.41 0-.39.39-.39 1.03 0 1.41l1.06 1.06c.39.39 1.03.39 1.41 0 .39-.39.39-1.03 0-1.41L5.99 4.58zm12.37 12.37c-.39-.39-1.03-.39-1.41 0-.39.39-.39 1.03 0 1.41l1.06 1.06c.39.39 1.03.39 1.41 0 .39-.39.39-1.03 0-1.41l-1.06-1.06zm1.06-10.96c.39-.39.39-1.03 0-1.41-.39-.39-1.03-.39-1.41 0l-1.06 1.06c-.39.39-.39 1.03 0 1.41.39.39 1.03.39 1.41 0l1.06-1.06zM7.05 18.36c.39-.39.39-1.03 0-1.41-.39-.39-1.03-.39-1.41 0l-1.06 1.06c-.39.39-.39 1.03 0 1.41.39.39 1.03.39 1.41 0l1.06-1.06z"/></svg>`;
    const moonIcon = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><path d="M12 3c-4.97 0-9 4.03-9 9s4.03 9 9 9 9-4.03 9-9c0-.46-.04-.92-.1-1.36-.98 1.37-2.58 2.26-4.4 2.26-3.03 0-5.5-2.47-5.5-5.5 0-1.82.89-3.42 2.26-4.4C12.92 3.04 12.46 3 12 3z"/></svg>`;

    function updateToggleIcon(theme) {
        if (themeToggleBtn) {
            themeToggleBtn.innerHTML = theme === 'dark' ? sunIcon : moonIcon;
        }
    }

    // Check local storage or system preference
    const currentTheme = localStorage.getItem('theme');
    const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;

    if (currentTheme) {
        htmlElement.setAttribute('data-theme', currentTheme);
        updateToggleIcon(currentTheme);
    } else if (prefersDark) {
        htmlElement.setAttribute('data-theme', 'dark');
        updateToggleIcon('dark');
    } else {
        htmlElement.setAttribute('data-theme', 'light');
        updateToggleIcon('light');
    }

    if (themeToggleBtn) {
        themeToggleBtn.addEventListener('click', () => {
            const theme = htmlElement.getAttribute('data-theme');
            const newTheme = theme === 'dark' ? 'light' : 'dark';

            htmlElement.setAttribute('data-theme', newTheme);
            localStorage.setItem('theme', newTheme);
            updateToggleIcon(newTheme);

            // Add a small rotation animation
            themeToggleBtn.style.transform = 'rotate(180deg)';
            setTimeout(() => {
                themeToggleBtn.style.transform = 'none';
            }, 300);
        });
    }

    // ---------------------------------------------------------------------
    // Avatar picker + cropper (signup / profile). Cropper.js is optional:
    // without it the raw image is used as-is, so the form still works.
    // ---------------------------------------------------------------------
    const trigger = document.getElementById('avatar-trigger');
    const fileInput = document.getElementById('avatar-input');
    const hiddenField = document.getElementById('id_avatar_base64');
    const preview = document.getElementById('avatar-preview');
    const placeholder = document.getElementById('avatar-placeholder');
    const modal = document.getElementById('cropperModal');
    const cropperImg = document.getElementById('cropperImage');
    let cropper = null;

    if (!trigger || !fileInput || !hiddenField) {
        return;
    }

    const MAX_BYTES = 3 * 1024 * 1024;

    function applyPreview(dataUrl) {
        hiddenField.value = dataUrl;
        if (preview) {
            preview.src = dataUrl;
            preview.style.display = 'block';
            preview.classList.add('pop-in');
        }
        if (placeholder) {
            placeholder.style.display = 'none';
        }
    }

    trigger.addEventListener('click', () => fileInput.click());

    fileInput.addEventListener('change', (event) => {
        const file = event.target.files[0];
        event.target.value = '';           // allow re-picking the same file
        if (!file) return;

        if (file.size > MAX_BYTES) {
            window.alert('Please choose an image smaller than 3 MB.');
            return;
        }

        const reader = new FileReader();
        reader.onload = (e) => {
            const dataUrl = e.target.result;

            if (typeof Cropper === 'undefined' || !modal || !cropperImg) {
                applyPreview(dataUrl);
                return;
            }

            cropperImg.src = dataUrl;
            modal.style.display = 'flex';
            if (cropper) cropper.destroy();
            cropper = new Cropper(cropperImg, { aspectRatio: 1, viewMode: 1, autoCropArea: 1 });
        };
        reader.readAsDataURL(file);
    });

    const cancelBtn = document.getElementById('btnCancelCrop');
    const applyBtn = document.getElementById('btnApplyCrop');

    if (cancelBtn) {
        cancelBtn.addEventListener('click', () => {
            modal.style.display = 'none';
            if (cropper) { cropper.destroy(); cropper = null; }
        });
    }

    if (applyBtn) {
        applyBtn.addEventListener('click', () => {
            if (!cropper) return;
            const canvas = cropper.getCroppedCanvas({ width: 250, height: 250 });
            applyPreview(canvas.toDataURL('image/jpeg', 0.8));
            modal.style.display = 'none';
            cropper.destroy();
            cropper = null;
        });
    }
});
