(function () {
    'use strict';

    const state = {
        jobId: null,
        stems: [],
        audioPlayers: new Map(),
        realGlassInstance: null,
        isProcessing: false,
    };

    const API_BASE = document.body.dataset.apiBase || '/api';

    const elements = {
        uploadForm: null,
        dropZone: null,
        audioFileInput: null,
        browseBtn: null,
        uploadBtn: null,
        selectedFileInfo: null,
        uploadProgress: null,
        progressFill: null,
        statusMessage: null,
        resultsSection: null,
        stemsContainer: null,
        convertMidiBtn: null,
        midiResult: null,
        stemCardTemplate: null,
    };

    const STEM_EMOJI = {
        drums: '🥁',
        bass: '🎸',
        vocals: '🎤',
        other: '🎹',
    };

    const ALLOWED_MIME_TYPES = new Set([
        'audio/mpeg',
        'audio/mp3',
        'audio/wav',
        'audio/x-wav',
        'audio/wave',
        'audio/flac',
        'audio/x-flac',
        'audio/ogg',
    ]);

    const ALLOWED_EXTENSIONS = new Set(['.mp3', '.wav', '.flac', '.ogg']);

    // API Client -----------------------------------------------------------
    async function uploadAndSeparate(file, options = {}) {
        const { onProgress } = options;
        const formData = new FormData();
        formData.append('file', file);

        if (typeof XMLHttpRequest !== 'undefined') {
            try {
                return await new Promise((resolve, reject) => {
                    const xhr = new XMLHttpRequest();
                    xhr.open('POST', `${API_BASE}/separate`);
                    xhr.responseType = 'json';

                    xhr.onload = () => {
                        const { status, statusText } = xhr;
                        let responseData = xhr.response;

                        if (!responseData && xhr.responseText) {
                            try {
                                responseData = JSON.parse(xhr.responseText);
                            } catch (_) {
                                responseData = null;
                            }
                        }

                        if (status >= 200 && status < 300) {
                            if (typeof onProgress === 'function') {
                                onProgress(1);
                            }
                            resolve(responseData ?? {});
                            return;
                        }

                        let message = `${status} ${statusText || 'Error'}`;
                        if (responseData?.message) {
                            message = responseData.message;
                        }
                        reject(new Error(`Upload failed: ${message}`));
                    };

                    xhr.onerror = () => {
                        reject(new Error('Network error while uploading the file.'));
                    };

                    xhr.onabort = () => {
                        reject(new Error('Upload was aborted.'));
                    };

                    if (xhr.upload && typeof onProgress === 'function') {
                        xhr.upload.onprogress = (event) => {
                            if (event.lengthComputable && event.total > 0) {
                                onProgress(event.loaded / event.total);
                            } else {
                                onProgress(null);
                            }
                        };
                    }

                    xhr.send(formData);
                });
            } catch (error) {
                if (error instanceof Error) {
                    throw error;
                }
                throw new Error('Upload failed due to an unexpected error.');
            }
        }

        const response = await fetch(`${API_BASE}/separate`, {
            method: 'POST',
            body: formData,
        });

        if (typeof onProgress === 'function') {
            onProgress(null);
        }

        if (!response.ok) {
            let message = `${response.status} ${response.statusText}`;
            try {
                const data = await response.json();
                if (data?.message) {
                    message = data.message;
                }
            } catch (_) {
                // ignored
            }
            throw new Error(`Upload failed: ${message}`);
        }

        const result = await response.json();
        if (typeof onProgress === 'function') {
            onProgress(1);
        }
        return result;
    }

    async function convertToMidi(jobId) {
        const response = await fetch(`${API_BASE}/convert-to-midi`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ job_id: jobId }),
        });

        if (!response.ok) {
            let message = `${response.status} ${response.statusText}`;
            try {
                const data = await response.json();
                if (data?.message) {
                    message = data.message;
                }
            } catch (_) {
                // ignored
            }
            throw new Error(`MIDI conversion failed: ${message}`);
        }

        return response.json();
    }

    function getDownloadUrl(jobId, category, filename) {
        return `${API_BASE}/download/${jobId}/${category}/${encodeURIComponent(filename)}`;
    }

    // UI Utilities ---------------------------------------------------------
    function showStatus(message, type = 'info') {
        elements.statusMessage.textContent = message;
        elements.statusMessage.className = `status-message show ${type}`;

        window.clearTimeout(elements.statusMessage._timeoutId);
        elements.statusMessage._timeoutId = window.setTimeout(() => {
            elements.statusMessage.classList.remove('show');
        }, 5000);
    }

    function updateProgressBar(value) {
        if (!elements.progressFill || !elements.uploadProgress) {
            return;
        }

        if (value === null) {
            elements.progressFill.style.width = '25%';
            elements.uploadProgress.setAttribute('aria-valuenow', '25');
            return;
        }

        const clamped = Math.max(0, Math.min(1, value));
        const percent = Math.round(clamped * 100);
        elements.progressFill.style.width = `${percent}%`;
        elements.uploadProgress.setAttribute('aria-valuenow', String(percent));
    }

    function showLoading(show = true) {
        if (show) {
            elements.uploadBtn.disabled = true;
            elements.uploadBtn.dataset.loading = 'true';
            elements.uploadBtn.textContent = 'Processing...';
            elements.uploadProgress.hidden = false;
            updateProgressBar(0);
        } else {
            const fileSelected = Boolean(elements.audioFileInput?.files?.length);
            elements.uploadBtn.disabled = !fileSelected;
            elements.uploadBtn.dataset.loading = 'false';
            elements.uploadBtn.textContent = 'Separate Audio';
            window.setTimeout(() => {
                elements.uploadProgress.hidden = true;
                updateProgressBar(0);
            }, 400);
        }
    }

    function getFileExtension(filename = '') {
        const lastDot = filename.lastIndexOf('.');
        if (lastDot === -1) {
            return '';
        }
        return filename.slice(lastDot).toLowerCase();
    }

    function isSupportedAudioFile(file) {
        if (!file) {
            return false;
        }

        const mimeType = (file.type || '').toLowerCase();
        if (mimeType && ALLOWED_MIME_TYPES.has(mimeType)) {
            return true;
        }

        const extension = getFileExtension(file.name);
        return extension ? ALLOWED_EXTENSIONS.has(extension) : false;
    }

    function formatFileSize(bytes) {
        if (!Number.isFinite(bytes) || bytes <= 0) {
            return 'Unknown size';
        }
        const units = ['B', 'KB', 'MB', 'GB', 'TB'];
        const exponent = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
        const value = bytes / Math.pow(1024, exponent);
        return `${value.toFixed(value >= 10 ? 0 : 2)} ${units[exponent]}`;
    }

    function formatTime(seconds) {
        if (!Number.isFinite(seconds) || seconds < 0) {
            return '0:00';
        }
        const minutes = Math.floor(seconds / 60);
        const secs = Math.floor(seconds % 60);
        return `${minutes}:${secs.toString().padStart(2, '0')}`;
    }

    function clearResults() {
        elements.stemsContainer.innerHTML = '';
        elements.resultsSection.hidden = true;
        elements.midiResult.hidden = true;
        elements.midiResult.innerHTML = '';
        elements.convertMidiBtn.disabled = true;

        state.stems = [];
        state.jobId = null;

        state.audioPlayers.forEach((player, key) => {
            destroyAudioPlayer(key, player);
        });
        state.audioPlayers.clear();
    }

    // RealGlass Integration ------------------------------------------------
    async function initRealGlass() {
        if (typeof RealGlass === 'undefined') {
            console.info('RealGlass unavailable – continuing without enhanced glass effects.');
            return null;
        }

        try {
            const rg = new RealGlass();
            await rg.init();
            state.realGlassInstance = rg;
            return rg;
        } catch (error) {
            console.warn('Failed to initialize RealGlass:', error);
            state.realGlassInstance = null;
            return null;
        }
    }

    async function applyGlassEffect(element, options = {}) {
        if (!state.realGlassInstance || !element) {
            return;
        }

        const defaults = {
            frosting: 0.2,
            borderRadius: 16,
            lightStrength: 1.8,
            glassOpacity: 0.3,
        };

        try {
            await state.realGlassInstance.apply(element, { ...defaults, ...options });
        } catch (error) {
            console.warn('RealGlass effect failed:', error);
        }
    }

    async function reapplyGlassEffects() {
        if (!state.realGlassInstance) {
            return;
        }

        const cards = document.querySelectorAll('.glass-card');
        for (const card of cards) {
            await applyGlassEffect(card);
        }
    }

    // Audio Player Management ----------------------------------------------
    function createAudioPlayer(stem) {
        const {
            name,
            filename,
            size,
            download_url: downloadUrl,
            download_url_encoded: downloadUrlEncoded,
        } = stem;
        const template = elements.stemCardTemplate.content.cloneNode(true);
        const card = template.querySelector('.stem-card');
        const audio = card.querySelector('audio');
        const playBtn = card.querySelector('.play-btn');
        const seekBar = card.querySelector('.seek-bar');
        const currentTime = card.querySelector('.current-time');
        const duration = card.querySelector('.duration');
        const volumeBtn = card.querySelector('.volume-btn');
        const volumeSlider = card.querySelector('.volume-slider');
        const downloadBtn = card.querySelector('.download-btn');
        const fileSizeEl = card.querySelector('.file-size');
        const nameEl = card.querySelector('.stem-name');

        card.dataset.stemName = name;
        const emoji = STEM_EMOJI[name?.toLowerCase()] || '🎼';
        nameEl.textContent = `${emoji} ${name}`;
        audio.src = downloadUrl || downloadUrlEncoded || getDownloadUrl(state.jobId, 'stems', filename);
        audio.preload = 'metadata';
        audio.controls = false;

        fileSizeEl.textContent = size ? formatFileSize(size) : '';
        downloadBtn.addEventListener('click', () => {
            const url = downloadUrl || downloadUrlEncoded || getDownloadUrl(state.jobId, 'stems', filename);
            window.open(url, '_blank');
        });

        playBtn.addEventListener('click', () => {
            const isPaused = audio.paused;
            pauseAllPlayers(name);
            if (isPaused) {
                audio.play().catch((error) => {
                    console.error('Playback failed:', error);
                    showStatus('Unable to play this stem. Please try downloading instead.', 'error');
                });
            } else {
                audio.pause();
            }
        });

        audio.addEventListener('play', () => {
            playBtn.textContent = '⏸️';
            playBtn.setAttribute('aria-label', 'Pause stem');
        });

        audio.addEventListener('pause', () => {
            playBtn.textContent = '▶️';
            playBtn.setAttribute('aria-label', 'Play stem');
        });

        audio.addEventListener('loadedmetadata', () => {
            if (audio.duration) {
                seekBar.max = Math.floor(audio.duration);
                duration.textContent = formatTime(audio.duration);
            }
        });

        audio.addEventListener('timeupdate', () => {
            if (!seekBar._isSeeking) {
                seekBar.value = Math.floor(audio.currentTime);
            }
            currentTime.textContent = formatTime(audio.currentTime);
        });

        seekBar.addEventListener('input', () => {
            seekBar._isSeeking = true;
            currentTime.textContent = formatTime(Number(seekBar.value));
        });

        seekBar.addEventListener('change', () => {
            audio.currentTime = Number(seekBar.value);
            seekBar._isSeeking = false;
        });

        volumeSlider.addEventListener('input', () => {
            audio.volume = Number(volumeSlider.value);
            if (audio.volume === 0) {
                volumeBtn.textContent = '🔇';
            } else if (audio.volume < 0.5) {
                volumeBtn.textContent = '🔉';
            } else {
                volumeBtn.textContent = '🔊';
            }
        });

        volumeBtn.addEventListener('click', () => {
            if (audio.muted || audio.volume === 0) {
                audio.muted = false;
                audio.volume = 1;
                volumeSlider.value = '1';
                volumeBtn.textContent = '🔊';
                volumeBtn.setAttribute('aria-label', 'Mute stem');
            } else {
                audio.muted = true;
                volumeBtn.textContent = '🔇';
                volumeBtn.setAttribute('aria-label', 'Unmute stem');
            }
        });

        audio.addEventListener('ended', () => {
            audio.currentTime = 0;
            audio.pause();
        });

        audio.addEventListener('error', () => {
            showStatus(`Error loading ${name} stem. Try downloading instead.`, 'error');
        });

        card.addEventListener('keydown', (event) => {
            if (event.code === 'Space') {
                event.preventDefault();
                playBtn.click();
            }
        });

        state.audioPlayers.set(name, { audio, playBtn, seekBar, volumeSlider, volumeBtn });
        return card;
    }

    function destroyAudioPlayer(name, player) {
        if (!player) {
            return;
        }
        const { audio, playBtn, seekBar, volumeSlider, volumeBtn } = player;
        audio.pause();
        audio.src = '';
        audio.load();

        playBtn?.replaceWith(playBtn.cloneNode(true));
        seekBar?.replaceWith(seekBar.cloneNode(true));
        volumeSlider?.replaceWith(volumeSlider.cloneNode(true));
        volumeBtn?.replaceWith(volumeBtn.cloneNode(true));
    }

    function pauseAllPlayers(exceptName = null) {
        state.audioPlayers.forEach((player, name) => {
            if (name === exceptName) {
                return;
            }
            player.audio.pause();
        });
    }

    // Rendering ------------------------------------------------------------
    function renderStems(stems) {
        elements.stemsContainer.innerHTML = '';
        const cards = stems.map((stem) => createAudioPlayer(stem));
        for (const card of cards) {
            elements.stemsContainer.appendChild(card);
        }
        elements.resultsSection.hidden = false;
        const hasJob = Boolean(state.jobId);
        const hasStems = Array.isArray(stems) && stems.length > 0;
        elements.convertMidiBtn.disabled = !(hasJob && hasStems);
        return cards;
    }

    function renderMidiResult(data) {
        const { midi_file: midiFile, stems_converted: stemsConverted } = data;
        elements.midiResult.innerHTML = '';

        const heading = document.createElement('h3');
        heading.textContent = 'MIDI File Ready';

        const info = document.createElement('p');
        info.textContent = midiFile?.filename ? `${midiFile.filename} (${formatFileSize(midiFile.size)})` : 'Download the combined MIDI file.';

        const downloadBtn = document.createElement('button');
        downloadBtn.type = 'button';
        downloadBtn.className = 'btn-primary';
        downloadBtn.textContent = '⬇️ Download MIDI';
        downloadBtn.addEventListener('click', () => {
            const midiFilename = midiFile?.filename;
            const url = midiFile?.download_url
                || midiFile?.download_url_encoded
                || (midiFilename ? getDownloadUrl(state.jobId, 'midi', midiFilename) : null);

            if (url) {
                window.open(url, '_blank');
            } else {
                showStatus('Unable to locate the MIDI file download link.', 'error');
            }
        });

        const list = document.createElement('ul');
        list.className = 'converted-stems';
        if (Array.isArray(stemsConverted) && stemsConverted.length > 0) {
            list.setAttribute('aria-label', 'Stems included in MIDI file');
            stemsConverted.forEach((stemName) => {
                const item = document.createElement('li');
                item.textContent = stemName;
                list.appendChild(item);
            });
        }

        elements.midiResult.append(heading, info, downloadBtn);
        if (list.childElementCount > 0) {
            elements.midiResult.appendChild(list);
        }
        elements.midiResult.hidden = false;
        return elements.midiResult;
    }

    // Event Handlers -------------------------------------------------------
    function handleFileSelect(file) {
        if (!file) {
            elements.selectedFileInfo.textContent = '';
            elements.uploadBtn.disabled = true;
            return;
        }

        if (!isSupportedAudioFile(file)) {
            showStatus('Unsupported file type. Please upload MP3, WAV, FLAC, or OGG.', 'error');
            elements.audioFileInput.value = '';
            elements.selectedFileInfo.textContent = '';
            elements.uploadBtn.disabled = true;
            return;
        }

        elements.selectedFileInfo.textContent = `${file.name} (${formatFileSize(file.size)})`;
        elements.uploadBtn.disabled = false;
    }

    function handleDragOver(event) {
        event.preventDefault();
        event.dataTransfer.dropEffect = 'copy';
        elements.dropZone.classList.add('dragging');
    }

    function handleDragLeave(event) {
        event.preventDefault();
        elements.dropZone.classList.remove('dragging');
    }

    function handleDrop(event) {
        event.preventDefault();
        elements.dropZone.classList.remove('dragging');
        const file = event.dataTransfer.files?.[0];
        if (file) {
            elements.audioFileInput.files = event.dataTransfer.files;
            handleFileSelect(file);
        }
    }

    async function handleUpload(event) {
        event.preventDefault();
        if (state.isProcessing) {
            return;
        }

        const file = elements.audioFileInput.files?.[0];
        if (!file) {
            showStatus('Please choose an audio file before uploading.', 'error');
            return;
        }

        state.isProcessing = true;
        showLoading(true);
        showStatus('Uploading and separating audio...', 'info');
        clearResults();

        try {
            const payload = await uploadAndSeparate(file, {
                onProgress: (progress) => {
                    if (progress == null) {
                        updateProgressBar(null);
                    } else {
                        updateProgressBar(progress);
                    }
                },
            });

            const responseData = payload?.data ?? {};
            state.jobId = responseData.job_id ?? null;
            state.stems = Array.isArray(responseData.stems) ? responseData.stems : [];
            const cards = renderStems(state.stems);
            showStatus('Audio separated successfully!', 'success');
            for (const card of cards) {
                await applyGlassEffect(card);
            }
        } catch (error) {
            console.error(error);
            showStatus(error.message || 'An unexpected error occurred.', 'error');
        } finally {
            state.isProcessing = false;
            showLoading(false);
        }
    }

    async function handleConvertToMidi() {
        if (state.isProcessing || !state.jobId) {
            return;
        }

        state.isProcessing = true;
        elements.convertMidiBtn.disabled = true;
        elements.convertMidiBtn.textContent = 'Converting...';
        showStatus('Converting stems to MIDI. This may take a moment...', 'info');

        try {
            const payload = await convertToMidi(state.jobId);
            const responseData = payload?.data ?? {};
            if (responseData.job_id) {
                state.jobId = responseData.job_id;
            }
            const resultCard = renderMidiResult(responseData);
            showStatus('MIDI file generated successfully!', 'success');
            await applyGlassEffect(resultCard, { glassOpacity: 0.35 });
        } catch (error) {
            console.error(error);
            showStatus(error.message || 'Unable to convert to MIDI at this time.', 'error');
        } finally {
            state.isProcessing = false;
            elements.convertMidiBtn.textContent = 'Convert All to MIDI';
            elements.convertMidiBtn.disabled = state.stems.length === 0;
        }
    }

    function bindEventListeners() {
        elements.browseBtn.addEventListener('click', () => {
            elements.audioFileInput.click();
        });

        elements.dropZone.addEventListener('click', (event) => {
            if (event.target !== elements.audioFileInput) {
                elements.audioFileInput.click();
            }
        });

        elements.dropZone.addEventListener('keydown', (event) => {
            if (event.key === 'Enter' || event.key === ' ' || event.code === 'Space') {
                event.preventDefault();
                elements.audioFileInput.click();
            }
        });

        elements.audioFileInput.addEventListener('change', () => {
            const file = elements.audioFileInput.files?.[0];
            handleFileSelect(file);
        });

        elements.uploadForm.addEventListener('submit', handleUpload);
        elements.convertMidiBtn.addEventListener('click', handleConvertToMidi);

        elements.dropZone.addEventListener('dragover', handleDragOver);
        elements.dropZone.addEventListener('dragleave', handleDragLeave);
        elements.dropZone.addEventListener('drop', handleDrop);

        window.addEventListener('unhandledrejection', (event) => {
            console.error('Unhandled rejection:', event.reason);
            showStatus('Something went wrong. Please try again.', 'error');
        });
    }

    async function init() {
        elements.uploadForm = document.getElementById('uploadForm');
        elements.dropZone = document.getElementById('dropZone');
        elements.audioFileInput = document.getElementById('audioFile');
        elements.browseBtn = document.getElementById('browseBtn');
        elements.uploadBtn = document.getElementById('uploadBtn');
        elements.selectedFileInfo = document.getElementById('selectedFileInfo');
        elements.uploadProgress = document.getElementById('uploadProgress');
        elements.progressFill = elements.uploadProgress.querySelector('.progress-bar-fill');
        elements.statusMessage = document.getElementById('statusMessage');
        elements.resultsSection = document.getElementById('resultsSection');
        elements.stemsContainer = document.getElementById('stemsContainer');
        elements.convertMidiBtn = document.getElementById('convertMidiBtn');
        elements.midiResult = document.getElementById('midiResult');
        elements.stemCardTemplate = document.getElementById('stemCardTemplate');

        bindEventListeners();
        await initRealGlass();

        const staticCards = document.querySelectorAll('.glass-card');
        for (const card of staticCards) {
            await applyGlassEffect(card);
        }

        console.info('MP3paraMIDI UI initialized.');
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
