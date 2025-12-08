/**
 * Preferences Tab JavaScript
 * Handles quiz, profile management, and evaluation UI
 */

// Global state
let quizState = {
    personName: '',
    currentPhase: 1,
    priorityRanking: [],
    thresholdResponses: {},
    pairwiseResponses: {},
    scenarios: [],
    currentScenarioIndex: 0,
};

let currentEditingProfile = null;
let cachedProfiles = [];
let cachedApartments = [];
let evalTableSortState = {
    column: 'score',  // Default sort by score
    ascending: false  // Descending by default
};

// Criteria definitions
const CRITERIA = [
    { id: 'safety', label: 'Safety', icon: '🛡️' },
    { id: 'commute', label: 'Commute', icon: '🚗' },
    { id: 'wfh_quality', label: 'WFH Quality', icon: '💻' },
    { id: 'parking', label: 'Parking', icon: '🅿️' },
    { id: 'gym', label: 'Gym', icon: '💪' },
    { id: 'space_luxury', label: 'Space & Luxury', icon: '🏠' },
    { id: 'laundry', label: 'Laundry', icon: '👕' },
    { id: 'happening', label: 'Happening-ness', icon: '🎉' },
    { id: 'price', label: 'Price', icon: '💰' },
];

// Preference strength options
const PREFERENCE_OPTIONS = [
    { value: 'STRONGLY_PREFER_A', label: 'Strongly prefer A', score: 9 },
    { value: 'MODERATELY_PREFER_A', label: 'Moderately prefer A', score: 7 },
    { value: 'SLIGHTLY_PREFER_A', label: 'Slightly prefer A', score: 5 },
    { value: 'WEAKLY_PREFER_A', label: 'Weakly prefer A', score: 3 },
    { value: 'EQUAL', label: 'Equal / No preference', score: 1 },
    { value: 'WEAKLY_PREFER_B', label: 'Weakly prefer B', score: 1/3 },
    { value: 'SLIGHTLY_PREFER_B', label: 'Slightly prefer B', score: 1/5 },
    { value: 'MODERATELY_PREFER_B', label: 'Moderately prefer B', score: 1/7 },
    { value: 'STRONGLY_PREFER_B', label: 'Strongly prefer B', score: 1/9 },
];

// Sub-tab navigation
function showPrefSubtab(tab) {
    // Remove active from all subtab buttons
    document.querySelectorAll('.pref-subtab').forEach(btn => btn.classList.remove('active'));
    
    // Hide all sections (remove active, add hidden)
    document.querySelectorAll('.pref-section').forEach(sec => {
        sec.classList.remove('active');
        sec.classList.add('hidden');
    });
    
    // Activate the selected subtab button
    document.querySelector(`.pref-subtab[onclick*="${tab}"]`).classList.add('active');
    
    // Show the selected section (add active, remove hidden)
    const sectionId = `pref${tab.charAt(0).toUpperCase() + tab.slice(1)}Section`;
    const section = document.getElementById(sectionId);
    if (section) {
        section.classList.add('active');
        section.classList.remove('hidden');
    }
    
    // Load data for specific tabs
    if (tab === 'profiles') {
        loadProfiles();
    } else if (tab === 'evaluate') {
        loadProfilesForEvaluation();
    }
}

// ================== PROFILES ==================

async function loadProfiles() {
    const container = document.getElementById('profilesList');
    container.innerHTML = '<div class="loading-spinner">Loading profiles...</div>';
    
    try {
        const response = await fetch('/preferences/api/profiles');
        const data = await response.json();
        
        if (!data.success) {
            throw new Error(data.error);
        }
        
        cachedProfiles = data.profiles;
        
        if (data.profiles.length === 0) {
            container.innerHTML = `
                <div class="empty-state">
                    <p>No profiles yet. Create one to get started!</p>
                </div>
            `;
            return;
        }
        
        container.innerHTML = data.profiles.map(profile => `
            <div class="profile-card">
                <div class="profile-card-header">
                    <h4>${profile.name}</h4>
                    <span class="profile-version">v${profile.version}</span>
                </div>
                <div class="profile-card-meta">
                    <p>${profile.criteria_count} criteria defined</p>
                    <p>Consistency: ${(profile.ahp_consistency * 100).toFixed(1)}%</p>
                    <p>Updated: ${new Date(profile.updated_at).toLocaleDateString()}</p>
                </div>
                <div class="profile-card-actions">
                    <button class="btn btn-small" onclick="editProfile('${profile.name}')">Edit</button>
                    <button class="btn btn-small btn-secondary" onclick="viewProfile('${profile.name}')">View</button>
                    <button class="btn btn-small btn-danger" onclick="deleteProfile('${profile.name}')">Delete</button>
                </div>
            </div>
        `).join('');
        
    } catch (error) {
        console.error('Error loading profiles:', error);
        container.innerHTML = `<div class="error">Error loading profiles: ${error.message}</div>`;
    }
}

async function createNewProfile() {
    const name = prompt('Enter name for the new profile:');
    if (!name) return;
    
    try {
        const response = await fetch('/preferences/api/profiles/create-default', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name }),
        });
        
        const data = await response.json();
        
        if (!data.success) {
            throw new Error(data.error);
        }
        
        alert(`Profile "${name}" created! You can now edit it or take the quiz to customize.`);
        loadProfiles();
        
    } catch (error) {
        console.error('Error creating profile:', error);
        alert('Error creating profile: ' + error.message);
    }
}

async function editProfile(name) {
    try {
        const response = await fetch(`/preferences/api/profiles/${encodeURIComponent(name)}`);
        const data = await response.json();
        
        if (!data.success) {
            throw new Error(data.error);
        }
        
        currentEditingProfile = data.profile;
        showProfileEditor(data.profile);
        
    } catch (error) {
        console.error('Error loading profile:', error);
        alert('Error loading profile: ' + error.message);
    }
}

function showProfileEditor(profile) {
    document.getElementById('profileEditorTitle').textContent = `Edit Profile: ${profile.person_name}`;
    document.getElementById('profileName').value = profile.person_name;
    document.getElementById('profileNotes').value = profile.notes || '';
    
    // Render criteria editor
    const editor = document.getElementById('criteriaEditor');
    const sortedCriteria = [...profile.criteria].sort((a, b) => a.priority_order - b.priority_order);
    
    editor.innerHTML = sortedCriteria.map((criterion, index) => {
        const idealValue = criterion.ideal?.[0]?.value || '';
        const acceptableValue = criterion.acceptable?.[0]?.value || '';
        const vetoValue = criterion.veto?.[0]?.value || '';
        
        return `
            <div class="criterion-item" draggable="true" data-id="${criterion.id}">
                <div class="criterion-header">
                    <strong>${criterion.display_name}</strong>
                    <span class="criterion-priority">Priority ${index + 1}</span>
                </div>
                <div class="threshold-inputs">
                    <div class="threshold-input">
                        <label>Ideal</label>
                        <input type="number" 
                               id="ideal_${criterion.id}" 
                               value="${idealValue}"
                               step="any">
                    </div>
                    <div class="threshold-input">
                        <label>Acceptable</label>
                        <input type="number" 
                               id="acceptable_${criterion.id}" 
                               value="${acceptableValue}"
                               step="any">
                    </div>
                    <div class="threshold-input">
                        <label>Veto</label>
                        <input type="number" 
                               id="veto_${criterion.id}" 
                               value="${vetoValue}"
                               step="any">
                    </div>
                </div>
            </div>
        `;
    }).join('');
    
    // Setup drag and drop
    setupCriteriaeDragDrop();
    
    document.getElementById('profileEditorModal').classList.remove('hidden');
}

function setupCriteriaeDragDrop() {
    const items = document.querySelectorAll('.criterion-item');
    
    items.forEach(item => {
        item.addEventListener('dragstart', (e) => {
            e.dataTransfer.setData('text/plain', item.dataset.id);
            item.classList.add('dragging');
        });
        
        item.addEventListener('dragend', () => {
            item.classList.remove('dragging');
            updateCriteriaPriorities();
        });
        
        item.addEventListener('dragover', (e) => {
            e.preventDefault();
            const dragging = document.querySelector('.dragging');
            if (dragging && dragging !== item) {
                const rect = item.getBoundingClientRect();
                const midY = rect.top + rect.height / 2;
                if (e.clientY < midY) {
                    item.parentNode.insertBefore(dragging, item);
                } else {
                    item.parentNode.insertBefore(dragging, item.nextSibling);
                }
            }
        });
    });
}

function updateCriteriaPriorities() {
    const items = document.querySelectorAll('.criterion-item');
    items.forEach((item, index) => {
        item.querySelector('.criterion-priority').textContent = `Priority ${index + 1}`;
    });
}

function closeProfileEditor() {
    document.getElementById('profileEditorModal').classList.add('hidden');
    currentEditingProfile = null;
}

async function saveProfile() {
    if (!currentEditingProfile) return;
    
    const name = document.getElementById('profileName').value.trim();
    const notes = document.getElementById('profileNotes').value.trim();
    
    // Collect criteria with new priorities and thresholds
    const items = document.querySelectorAll('.criterion-item');
    const criteria = [];
    
    items.forEach((item, index) => {
        const id = item.dataset.id;
        const originalCriterion = currentEditingProfile.criteria.find(c => c.id === id);
        
        const idealValue = parseFloat(document.getElementById(`ideal_${id}`).value);
        const acceptableValue = parseFloat(document.getElementById(`acceptable_${id}`).value);
        const vetoValue = parseFloat(document.getElementById(`veto_${id}`).value);
        
        // Determine operator based on criterion type
        const isLowerBetter = ['commute', 'gym', 'price'].includes(id);
        const operator = isLowerBetter ? 'lte' : 'gte';
        
        criteria.push({
            id: id,
            display_name: originalCriterion.display_name,
            priority_order: index + 1,
            ideal: !isNaN(idealValue) ? [{ field: originalCriterion.ideal?.[0]?.field || id + '_score', value: idealValue, operator }] : [],
            acceptable: !isNaN(acceptableValue) ? [{ field: originalCriterion.acceptable?.[0]?.field || id + '_score', value: acceptableValue, operator }] : [],
            veto: !isNaN(vetoValue) ? [{ field: originalCriterion.veto?.[0]?.field || id + '_score', value: vetoValue, operator }] : [],
            veto_reason: originalCriterion.veto_reason || '',
        });
    });
    
    try {
        const response = await fetch(`/preferences/api/profiles/${encodeURIComponent(name)}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                criteria,
                notes,
                ahp_weights: currentEditingProfile.ahp_weights,
                ahp_consistency_ratio: currentEditingProfile.ahp_consistency_ratio,
            }),
        });
        
        const data = await response.json();
        
        if (!data.success) {
            throw new Error(data.error);
        }
        
        alert('Profile saved successfully!');
        closeProfileEditor();
        loadProfiles();
        
    } catch (error) {
        console.error('Error saving profile:', error);
        alert('Error saving profile: ' + error.message);
    }
}

async function viewProfile(name) {
    try {
        const response = await fetch(`/preferences/api/profiles/${encodeURIComponent(name)}`);
        const data = await response.json();
        
        if (!data.success) {
            throw new Error(data.error);
        }
        
        const profile = data.profile;
        const criteria = profile.criteria.sort((a, b) => a.priority_order - b.priority_order);
        
        // Build detailed profile view HTML
        const weightsHtml = Object.entries(profile.ahp_weights)
            .sort((a, b) => b[1] - a[1])
            .map(([key, value]) => `
                <div class="weight-item">
                    <span>${key.replace('_', ' ')}</span>
                    <div class="weight-bar" style="width: ${value * 100}%"></div>
                    <span>${(value * 100).toFixed(1)}%</span>
                </div>
            `).join('');
        
        const criteriaHtml = criteria.map((c, i) => {
            const idealVal = c.ideal?.[0]?.value || 'N/A';
            const acceptVal = c.acceptable?.[0]?.value || 'N/A';
            const vetoVal = c.veto?.[0]?.value || 'N/A';
            const operator = c.ideal?.[0]?.operator || '';
            
            return `
                <div class="criterion-detail">
                    <div class="criterion-header-view">
                        <span class="priority-badge">#${i + 1}</span>
                        <strong>${c.display_name}</strong>
                    </div>
                    <div class="threshold-values">
                        <span class="tier-ideal">Ideal: ${operator} ${idealVal}</span>
                        <span class="tier-acceptable">OK: ${operator} ${acceptVal}</span>
                        <span class="tier-veto">${vetoVal !== 'N/A' ? `Veto: ${operator} ${vetoVal}` : 'No veto'}</span>
                    </div>
                    ${c.veto_reason ? `<small class="veto-reason">${c.veto_reason}</small>` : ''}
                </div>
            `;
        }).join('');
        
        document.getElementById('profileViewTitle').textContent = `Profile: ${profile.person_name}`;
        document.getElementById('profileViewContent').innerHTML = `
            <div class="profile-view-section">
                <h4>📊 Priority Weights (AHP)</h4>
                <p style="font-size: 0.9em; color: #666;">Consistency: ${(profile.ahp_consistency_ratio * 100).toFixed(1)}%</p>
                <div class="weights-list">
                    ${weightsHtml}
                </div>
            </div>
            
            <div class="profile-view-section">
                <h4>📋 Criteria & Thresholds</h4>
                <div class="criteria-list-view">
                    ${criteriaHtml}
                </div>
            </div>
            
            ${profile.notes ? `
                <div class="profile-view-section">
                    <h4>📝 Notes</h4>
                    <p>${profile.notes}</p>
                </div>
            ` : ''}
        `;
        
        document.getElementById('profileViewModal').classList.remove('hidden');
        
    } catch (error) {
        console.error('Error viewing profile:', error);
        alert('Error viewing profile: ' + error.message);
    }
}

function closeProfileViewModal() {
    document.getElementById('profileViewModal').classList.add('hidden');
}

async function deleteProfile(name) {
    if (!confirm(`Are you sure you want to delete the profile "${name}"?`)) {
        return;
    }
    
    try {
        const response = await fetch(`/preferences/api/profiles/${encodeURIComponent(name)}`, {
            method: 'DELETE',
        });
        
        const data = await response.json();
        
        if (!data.success) {
            throw new Error(data.error);
        }
        
        alert('Profile deleted.');
        loadProfiles();
        
    } catch (error) {
        console.error('Error deleting profile:', error);
        alert('Error deleting profile: ' + error.message);
    }
}

// ================== QUIZ ==================

async function startQuiz() {
    const name = document.getElementById('quizPersonName').value.trim();
    if (!name) {
        alert('Please enter your name.');
        return;
    }
    
    quizState.personName = name;
    quizState.currentPhase = 1;
    quizState.priorityRanking = CRITERIA.map(c => c.id);
    quizState.thresholdResponses = {};
    quizState.pairwiseResponses = {};
    
    // Load scenarios
    try {
        const response = await fetch('/preferences/api/quiz/scenarios');
        const data = await response.json();
        
        if (!data.success) {
            throw new Error(data.error);
        }
        
        quizState.scenarios = data.scenarios;
        quizState.currentScenarioIndex = 0;
        
    } catch (error) {
        console.error('Error loading scenarios:', error);
        alert('Error loading quiz scenarios: ' + error.message);
        return;
    }
    
    // Load threshold questions
    try {
        const response = await fetch('/preferences/api/quiz/threshold-questions');
        const data = await response.json();
        
        if (!data.success) {
            throw new Error(data.error);
        }
        
        renderThresholdQuestions(data.questions);
        
    } catch (error) {
        console.error('Error loading threshold questions:', error);
    }
    
    // Setup UI
    document.querySelector('.quiz-setup').classList.add('hidden');
    document.getElementById('quizContainer').classList.remove('hidden');
    
    renderPriorityRanking();
    showQuizPhase(1);
}

function renderPriorityRanking() {
    const container = document.getElementById('priorityRanking');
    
    container.innerHTML = quizState.priorityRanking.map((id, index) => {
        const criterion = CRITERIA.find(c => c.id === id);
        return `
            <div class="priority-item" draggable="true" data-id="${id}">
                <span class="priority-number">${index + 1}</span>
                <span class="priority-label">${criterion.icon} ${criterion.label}</span>
                <span class="priority-handle">⋮⋮</span>
            </div>
        `;
    }).join('');
    
    // Setup drag and drop
    setupPriorityDragDrop();
}

function setupPriorityDragDrop() {
    const items = document.querySelectorAll('.priority-item');
    
    items.forEach(item => {
        item.addEventListener('dragstart', (e) => {
            e.dataTransfer.setData('text/plain', item.dataset.id);
            item.classList.add('dragging');
        });
        
        item.addEventListener('dragend', () => {
            item.classList.remove('dragging');
            updatePriorityOrder();
        });
        
        item.addEventListener('dragover', (e) => {
            e.preventDefault();
            const dragging = document.querySelector('.priority-item.dragging');
            if (dragging && dragging !== item) {
                const rect = item.getBoundingClientRect();
                const midY = rect.top + rect.height / 2;
                if (e.clientY < midY) {
                    item.parentNode.insertBefore(dragging, item);
                } else {
                    item.parentNode.insertBefore(dragging, item.nextSibling);
                }
            }
        });
    });
}

function updatePriorityOrder() {
    const items = document.querySelectorAll('.priority-item');
    quizState.priorityRanking = [];
    
    items.forEach((item, index) => {
        quizState.priorityRanking.push(item.dataset.id);
        item.querySelector('.priority-number').textContent = index + 1;
    });
}

function renderThresholdQuestions(questions) {
    const container = document.getElementById('thresholdQuestions');
    
    container.innerHTML = questions.map(q => `
        <div class="threshold-question" data-question-id="${q.id}">
            <label>${q.question}</label>
            <div class="threshold-sliders">
                <div class="threshold-slider-group">
                    <span>Ideal</span>
                    <input type="number" 
                           id="thresh_ideal_${q.id}" 
                           value="${q.default_ideal}"
                           min="${q.min_value}"
                           max="${q.max_value}"
                           step="${q.step}">
                    <small>${q.unit}</small>
                </div>
                <div class="threshold-slider-group">
                    <span>Acceptable</span>
                    <input type="number" 
                           id="thresh_acceptable_${q.id}" 
                           value="${q.default_acceptable}"
                           min="${q.min_value}"
                           max="${q.max_value}"
                           step="${q.step}">
                    <small>${q.unit}</small>
                </div>
                <div class="threshold-slider-group">
                    <span>Veto</span>
                    <input type="number" 
                           id="thresh_veto_${q.id}" 
                           value="${q.default_veto}"
                           min="${q.min_value}"
                           max="${q.max_value}"
                           step="${q.step}">
                    <small>${q.unit}</small>
                </div>
            </div>
        </div>
    `).join('');
}

function showQuizPhase(phase) {
    quizState.currentPhase = phase;
    
    // Hide all phases (remove active, add hidden)
    document.querySelectorAll('.quiz-phase').forEach(p => {
        p.classList.remove('active');
        p.classList.add('hidden');
    });
    document.getElementById('quizResults').classList.add('hidden');
    
    // Show current phase (add active, remove hidden)
    const phaseElement = document.getElementById(`quizPhase${phase}`);
    if (phaseElement) {
        phaseElement.classList.add('active');
        phaseElement.classList.remove('hidden');
    }
    
    // Update progress
    const progress = (phase / 3) * 100;
    document.getElementById('quizProgressFill').style.width = `${progress}%`;
    
    const phaseNames = ['', 'Priority Ranking', 'Thresholds', 'Trade-off Scenarios'];
    document.getElementById('quizProgressText').textContent = `Step ${phase} of 3: ${phaseNames[phase]}`;
    
    if (phase === 3) {
        renderCurrentScenario();
    }
}

function nextQuizPhase(phase) {
    if (phase === 2) {
        // Collect threshold responses before moving to phase 3
        collectThresholdResponses();
    }
    
    if (phase > 3) {
        // Quiz complete
        submitQuiz();
    } else {
        showQuizPhase(phase);
    }
}

function previousQuizPhase(phase) {
    showQuizPhase(phase);
}

function collectThresholdResponses() {
    document.querySelectorAll('.threshold-question').forEach(q => {
        const questionId = q.dataset.questionId;
        quizState.thresholdResponses[questionId] = {
            ideal: parseFloat(document.getElementById(`thresh_ideal_${questionId}`).value),
            acceptable: parseFloat(document.getElementById(`thresh_acceptable_${questionId}`).value),
            veto: parseFloat(document.getElementById(`thresh_veto_${questionId}`).value),
        };
    });
}

function renderCurrentScenario() {
    const scenario = quizState.scenarios[quizState.currentScenarioIndex];
    if (!scenario) return;
    
    const container = document.getElementById('scenarioContainer');
    const currentResponse = quizState.pairwiseResponses[scenario.id];
    
    container.innerHTML = `
        <div class="scenario-title">${scenario.description}</div>
        ${scenario.context ? `<div class="scenario-context">${scenario.context}</div>` : ''}
        
        <div class="scenario-options">
            <div class="scenario-option">
                <h5>Option A (${scenario.criterion_a})</h5>
                <p>${scenario.option_a_description}</p>
            </div>
            <div class="scenario-option">
                <h5>Option B (${scenario.criterion_b})</h5>
                <p>${scenario.option_b_description}</p>
            </div>
        </div>
        
        <div class="preference-scale">
            ${PREFERENCE_OPTIONS.map(opt => `
                <div class="preference-option ${currentResponse === opt.value ? 'selected' : ''}"
                     onclick="selectPreference('${scenario.id}', '${opt.value}')">
                    <input type="radio" 
                           name="pref_${scenario.id}" 
                           value="${opt.value}"
                           ${currentResponse === opt.value ? 'checked' : ''}>
                    <label>${opt.label}</label>
                </div>
            `).join('')}
        </div>
    `;
    
    // Update counter
    document.getElementById('scenarioCounter').textContent = 
        `${quizState.currentScenarioIndex + 1} / ${quizState.scenarios.length}`;
    
    // Update buttons
    document.getElementById('prevScenarioBtn').disabled = quizState.currentScenarioIndex === 0;
    document.getElementById('nextScenarioBtn').textContent = 
        quizState.currentScenarioIndex === quizState.scenarios.length - 1 ? 'Finish Quiz' : 'Next →';
}

function selectPreference(scenarioId, value) {
    quizState.pairwiseResponses[scenarioId] = value;
    renderCurrentScenario();
}

function previousScenario() {
    if (quizState.currentScenarioIndex > 0) {
        quizState.currentScenarioIndex--;
        renderCurrentScenario();
    }
}

function nextScenario() {
    if (quizState.currentScenarioIndex < quizState.scenarios.length - 1) {
        quizState.currentScenarioIndex++;
        renderCurrentScenario();
    } else {
        // All scenarios complete
        submitQuiz();
    }
}

async function submitQuiz() {
    // Collect final threshold responses
    collectThresholdResponses();
    
    try {
        const response = await fetch('/preferences/api/quiz/submit', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                person_name: quizState.personName,
                priority_ranking: quizState.priorityRanking,
                threshold_responses: quizState.thresholdResponses,
                pairwise_responses: quizState.pairwiseResponses,
            }),
        });
        
        const data = await response.json();
        
        if (!data.success) {
            throw new Error(data.error);
        }
        
        // Show results
        showQuizResults(data);
        
    } catch (error) {
        console.error('Error submitting quiz:', error);
        alert('Error submitting quiz: ' + error.message);
    }
}

function showQuizResults(data) {
    // Hide all phases
    document.querySelectorAll('.quiz-phase').forEach(p => {
        p.classList.remove('active');
        p.classList.add('hidden');
    });
    // Show results
    document.getElementById('quizResults').classList.remove('hidden');
    
    const weightsHtml = Object.entries(data.ahp_weights)
        .sort((a, b) => b[1] - a[1])
        .map(([key, value]) => `
            <div class="weight-item">
                <strong>${key.replace('_', ' ')}</strong>
                <span>${(value * 100).toFixed(1)}%</span>
            </div>
        `).join('');
    
    const consistencyClass = data.is_consistent ? 'good' : 'poor';
    const consistencyText = data.is_consistent 
        ? '✓ Your responses are consistent' 
        : '⚠️ Some responses may be inconsistent';
    
    document.getElementById('quizResultsContent').innerHTML = `
        <div class="consistency-badge ${consistencyClass}">${consistencyText}</div>
        <p>Consistency Ratio: ${(data.consistency_ratio * 100).toFixed(1)}% ${data.is_consistent ? '(< 10% is good)' : '(> 10% may indicate inconsistency)'}</p>
        
        <h5>Derived Weights:</h5>
        <div class="results-weights">
            ${weightsHtml}
        </div>
        
        <p style="margin-top: 20px;">Profile saved for <strong>${quizState.personName}</strong>!</p>
    `;
}

function saveQuizProfile() {
    // Already saved during submitQuiz
    alert('Profile already saved!');
    
    // Reset and go back to profiles
    document.getElementById('quizContainer').classList.add('hidden');
    document.querySelector('.quiz-setup').classList.remove('hidden');
    document.getElementById('quizPersonName').value = '';
    
    showPrefSubtab('profiles');
}

// ================== EVALUATION ==================

async function loadProfilesForEvaluation() {
    try {
        const response = await fetch('/preferences/api/profiles');
        const data = await response.json();
        
        if (!data.success) {
            throw new Error(data.error);
        }
        
        cachedProfiles = data.profiles;
        
        const container = document.getElementById('evalProfileCheckboxes');
        container.innerHTML = data.profiles.map(profile => `
            <label class="profile-checkbox">
                <input type="checkbox" value="${profile.name}" checked>
                ${profile.name}
            </label>
        `).join('');
        
    } catch (error) {
        console.error('Error loading profiles for evaluation:', error);
    }
}

// Store max vetoes setting globally so renderEvaluationResults can access it
let currentMaxVetoes = 0;

async function runPreferenceEvaluation() {
    // Get selected profiles
    const checkboxes = document.querySelectorAll('#evalProfileCheckboxes input[type="checkbox"]:checked');
    const profileNames = Array.from(checkboxes).map(cb => cb.value);
    
    if (profileNames.length === 0) {
        alert('Please select at least one profile to evaluate against.');
        return;
    }
    
    // Get excluded categories
    const excludeCheckboxes = document.querySelectorAll('#evalExcludeCategoriesCheckboxes input[type="checkbox"]:checked');
    const excludedCategories = Array.from(excludeCheckboxes).map(cb => cb.value);
    
    const maxVetoes = parseInt(document.getElementById('evalMaxVetoes').value);
    const topN = parseInt(document.getElementById('evalTopN').value);
    
    // Store for use in rendering
    currentMaxVetoes = maxVetoes;
    
    try {
        // Show loading state
        document.getElementById('evalResults').classList.remove('hidden');
        document.getElementById('evalSummaryContent').innerHTML = '<div class="loading-spinner">Evaluating apartments...</div>';
        document.getElementById('evalShortlistContent').innerHTML = '';
        document.getElementById('evalTableBody').innerHTML = '';
        
        const response = await fetch('/preferences/api/evaluate-from-sheet', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                profiles: profileNames,
                max_vetoes: maxVetoes,
                top_n: topN,
                excluded_categories: excludedCategories,
            }),
        });
        
        const data = await response.json();
        
        if (!data.success) {
            throw new Error(data.error);
        }
        
        renderEvaluationResults(data);
        
    } catch (error) {
        console.error('Error running evaluation:', error);
        document.getElementById('evalSummaryContent').innerHTML = `<div class="error">Error: ${error.message}</div>`;
    }
}

function renderEvaluationResults(data) {
    // Summary
    const summary = data.summary;
    document.getElementById('evalSummaryContent').innerHTML = `
        <h4>Evaluation Summary</h4>
        <div class="summary-stats">
            <div class="summary-stat">
                <div class="summary-stat-value">${summary.summary.total_apartments}</div>
                <div class="summary-stat-label">Total Apartments</div>
            </div>
            <div class="summary-stat">
                <div class="summary-stat-value">${summary.summary.passing_apartments}</div>
                <div class="summary-stat-label">Passing</div>
            </div>
            <div class="summary-stat">
                <div class="summary-stat-value">${summary.summary.vetoed_apartments}</div>
                <div class="summary-stat-label">Vetoed</div>
            </div>
            <div class="summary-stat">
                <div class="summary-stat-value">${summary.summary.pass_rate}%</div>
                <div class="summary-stat-label">Pass Rate</div>
            </div>
        </div>
    `;
    
    // Shortlist
    const shortlistHtml = data.shortlist.map((eval_, index) => `
        <div class="shortlist-item">
            <div class="shortlist-rank">${index + 1}</div>
            <div class="shortlist-info">
                <div class="shortlist-address">${eval_.apartment_id}</div>
                <div class="shortlist-meta">
                    ${Object.entries(eval_.individual_evaluations).map(([name, e]) => 
                        `${name}: ${(e.tie_break_score * 100).toFixed(0)}%`
                    ).join(' | ')}
                </div>
            </div>
            <div class="shortlist-score">${(eval_.joint_satisfaction_score * 100).toFixed(0)}%</div>
        </div>
    `).join('');
    
    document.getElementById('evalShortlistContent').innerHTML = shortlistHtml || '<p>No apartments passed all criteria.</p>';
    
    // Full results table
    const tableHtml = data.evaluations.map(eval_ => {
        // Determine if this apartment should be marked as veto based on max_vetoes threshold
        const isVeto = eval_.joint_veto_count > currentMaxVetoes;
        
        return `
        <tr>
            <td>${eval_.rank || '-'}</td>
            <td>${eval_.apartment_id}</td>
            <td>${(eval_.joint_satisfaction_score * 100).toFixed(1)}%</td>
            <td>${eval_.joint_veto_count}</td>
            <td class="${isVeto ? 'status-veto' : 'status-ok'}">
                ${isVeto ? '✗ VETO' : '✓ OK'}
            </td>
            <td>
                <button class="btn btn-small" onclick="showEvalDetail('${eval_.apartment_id}')">Details</button>
            </td>
        </tr>
        `;
    }).join('');
    
    document.getElementById('evalTableBody').innerHTML = tableHtml;
    
    // Store evaluations for detail view
    cachedApartments = data.evaluations;
    
    // Update sort indicators
    updateEvalTableSortIndicators();
}

function sortEvalTable(column) {
    // Toggle sort direction if clicking same column, otherwise default to descending
    if (evalTableSortState.column === column) {
        evalTableSortState.ascending = !evalTableSortState.ascending;
    } else {
        evalTableSortState.column = column;
        evalTableSortState.ascending = (column === 'apartment'); // Apartment ascending by default, others descending
    }
    
    // Sort the cached apartments
    const sorted = [...cachedApartments].sort((a, b) => {
        let aVal, bVal;
        
        switch(column) {
            case 'rank':
                aVal = a.rank || 999;
                bVal = b.rank || 999;
                break;
            case 'apartment':
                aVal = a.apartment_id.toLowerCase();
                bVal = b.apartment_id.toLowerCase();
                break;
            case 'score':
                aVal = a.joint_satisfaction_score || 0;
                bVal = b.joint_satisfaction_score || 0;
                break;
            case 'vetoes':
                aVal = a.joint_veto_count || 0;
                bVal = b.joint_veto_count || 0;
                break;
            case 'status':
                // Sort by veto status (OK before VETO)
                const aIsVeto = a.joint_veto_count > currentMaxVetoes;
                const bIsVeto = b.joint_veto_count > currentMaxVetoes;
                aVal = aIsVeto ? 1 : 0;
                bVal = bIsVeto ? 1 : 0;
                break;
            default:
                return 0;
        }
        
        // Compare
        let comparison = 0;
        if (aVal < bVal) comparison = -1;
        if (aVal > bVal) comparison = 1;
        
        return evalTableSortState.ascending ? comparison : -comparison;
    });
    
    // Re-render table with sorted data
    const tableHtml = sorted.map(eval_ => {
        const isVeto = eval_.joint_veto_count > currentMaxVetoes;
        
        return `
        <tr>
            <td>${eval_.rank || '-'}</td>
            <td>${eval_.apartment_id}</td>
            <td>${(eval_.joint_satisfaction_score * 100).toFixed(1)}%</td>
            <td>${eval_.joint_veto_count}</td>
            <td class="${isVeto ? 'status-veto' : 'status-ok'}">
                ${isVeto ? '✗ VETO' : '✓ OK'}
            </td>
            <td>
                <button class="btn btn-small" onclick="showEvalDetail('${eval_.apartment_id}')">Details</button>
            </td>
        </tr>
        `;
    }).join('');
    
    document.getElementById('evalTableBody').innerHTML = tableHtml;
    
    // Update sort indicators
    updateEvalTableSortIndicators();
}

function updateEvalTableSortIndicators() {
    // Remove active class from all headers
    document.querySelectorAll('.eval-table th.sortable-header').forEach(th => {
        th.classList.remove('active');
        const indicator = th.querySelector('.sort-indicator');
        if (indicator) indicator.textContent = '';
    });
    
    // Add active class and indicator to current sort column
    const columnMap = {
        'rank': 0,
        'apartment': 1,
        'score': 2,
        'vetoes': 3,
        'status': 4
    };
    
    const headerIndex = columnMap[evalTableSortState.column];
    if (headerIndex !== undefined) {
        const headers = document.querySelectorAll('.eval-table th.sortable-header');
        if (headers[headerIndex]) {
            headers[headerIndex].classList.add('active');
            const indicator = headers[headerIndex].querySelector('.sort-indicator');
            if (indicator) {
                indicator.textContent = evalTableSortState.ascending ? '▲' : '▼';
            }
        }
    }
}

async function showEvalDetail(apartmentId) {
    const eval_ = cachedApartments.find(e => e.apartment_id === apartmentId);
    if (!eval_) return;
    
    document.getElementById('prefDetailTitle').textContent = `Evaluation: ${apartmentId}`;
    
    let html = `
        <div class="eval-detail-tabs">
            <button class="eval-detail-tab active" onclick="switchEvalDetailTab('evaluation')">📊 Preference Evaluation</button>
            <button class="eval-detail-tab" onclick="switchEvalDetailTab('analysis')">🏠 Apartment Analysis</button>
        </div>
    `;
    
    // Evaluation Content (default view)
    html += '<div id="evalDetailEvaluation" class="eval-detail-content active">';
    
    // Per-person breakdown
    for (const [personName, individual] of Object.entries(eval_.individual_evaluations)) {
        html += `
            <div class="detail-section">
                <h5>${personName}'s Evaluation</h5>
                <p>Score: ${(individual.tie_break_score * 100).toFixed(1)}%</p>
                <p>Ideal: ${individual.ideal_count} | Acceptable: ${individual.acceptable_count} | Veto: ${individual.veto_count}</p>
                
                <div class="tier-results">
                    ${Object.entries(individual.tier_results).map(([criterion, tier]) => `
                        <div class="tier-result">
                            <span>${criterion}</span>
                            <span class="tier-badge ${tier}">${tier.toUpperCase()}</span>
                        </div>
                    `).join('')}
                </div>
                
                ${individual.first_violation ? `
                    <p style="margin-top: 12px; color: #dc3545;">
                        First violation: ${individual.first_violation.criterion_name} (Priority ${individual.first_violation.priority_order})
                    </p>
                ` : ''}
            </div>
        `;
    }
    
    // Disagreements
    if (eval_.disagreements && eval_.disagreements.length > 0) {
        html += `
            <div class="detail-section">
                <h5>Areas of Disagreement</h5>
                ${eval_.disagreements.map(d => `
                    <p>${d.criterion_id}: ${Object.entries(d.tiers_by_person).map(([p, t]) => `${p}: ${t}`).join(', ')}</p>
                `).join('')}
            </div>
        `;
    }
    
    html += '</div>'; // Close evaluation content
    
    // Analysis Content (will be loaded async)
    html += '<div id="evalDetailAnalysis" class="eval-detail-content hidden"><div class="loading-spinner">Loading apartment details...</div></div>';
    
    document.getElementById('prefDetailContent').innerHTML = html;
    document.getElementById('prefDetailModal').classList.remove('hidden');
    
    // Load apartment analysis data asynchronously
    try {
        const response = await fetch('/get_apartment_list');
        const apartments = await response.json();
        
        // Find the apartment by address
        const apartment = apartments.find(apt => apt.address === apartmentId);
        
        if (apartment) {
            // Build rich detail HTML similar to the Analysis tab
            const analysisHtml = buildApartmentAnalysisHTML(apartment);
            document.getElementById('evalDetailAnalysis').innerHTML = analysisHtml;
        } else {
            document.getElementById('evalDetailAnalysis').innerHTML = '<p>Apartment details not found.</p>';
        }
    } catch (error) {
        console.error('Error loading apartment analysis:', error);
        document.getElementById('evalDetailAnalysis').innerHTML = '<p>Error loading apartment details.</p>';
    }
}

function switchEvalDetailTab(tabName) {
    // Update tab buttons
    document.querySelectorAll('.eval-detail-tab').forEach(tab => {
        tab.classList.remove('active');
    });
    event.target.classList.add('active');
    
    // Update content
    document.querySelectorAll('.eval-detail-content').forEach(content => {
        content.classList.add('hidden');
    });
    document.getElementById(`evalDetail${tabName.charAt(0).toUpperCase() + tabName.slice(1)}`).classList.remove('hidden');
}

function buildApartmentAnalysisHTML(apartment) {
    // Build a simplified version of the detail panel for the modal
    return `
        <div class="apartment-analysis-summary" style="padding: 16px;">
            <div class="score-overview" style="background: #f5f5f7; padding: 16px; border-radius: 8px; margin-bottom: 16px;">
                <h4 style="margin: 0 0 12px 0;">Overall Score</h4>
                <div style="font-size: 32px; font-weight: 600; color: #0066cc;">${apartment.score || 'N/A'}</div>
                ${apartment.score_min && apartment.score_max ? `
                    <div style="font-size: 14px; color: #86868b;">Range: ${apartment.score_min} - ${apartment.score_max}</div>
                ` : ''}
            </div>
            
            <div class="score-breakdown">
                <h4>Score Breakdown</h4>
                <div class="component-scores" style="display: grid; gap: 12px;">
                    ${apartment.commute_score !== undefined ? `
                        <div style="display: flex; justify-content: space-between; padding: 8px; background: #f5f5f7; border-radius: 6px;">
                            <span>🚗 Commute</span>
                            <strong>${apartment.commute_score}</strong>
                        </div>
                    ` : ''}
                    ${apartment.safety_score !== undefined ? `
                        <div style="display: flex; justify-content: space-between; padding: 8px; background: #f5f5f7; border-radius: 6px;">
                            <span>🛡️ Safety</span>
                            <strong>${apartment.safety_score}</strong>
                        </div>
                    ` : ''}
                    ${apartment.wfh_score !== undefined ? `
                        <div style="display: flex; justify-content: space-between; padding: 8px; background: #f5f5f7; border-radius: 6px;">
                            <span>💻 WFH Quality</span>
                            <strong>${apartment.wfh_score}</strong>
                        </div>
                    ` : ''}
                    ${apartment.happening_score !== undefined ? `
                        <div style="display: flex; justify-content: space-between; padding: 8px; background: #f5f5f7; border-radius: 6px;">
                            <span>🎉 Happening</span>
                            <strong>${apartment.happening_score}</strong>
                        </div>
                    ` : ''}
                    ${apartment.parking_score !== undefined ? `
                        <div style="display: flex; justify-content: space-between; padding: 8px; background: #f5f5f7; border-radius: 6px;">
                            <span>🅿️ Parking</span>
                            <strong>${apartment.parking_score}</strong>
                        </div>
                    ` : ''}
                    ${apartment.gym_score !== undefined ? `
                        <div style="display: flex; justify-content: space-between; padding: 8px; background: #f5f5f7; border-radius: 6px;">
                            <span>🏋️ Gym</span>
                            <strong>${apartment.gym_score}</strong>
                        </div>
                    ` : ''}
                    ${apartment.laundry_score !== undefined ? `
                        <div style="display: flex; justify-content: space-between; padding: 8px; background: #f5f5f7; border-radius: 6px;">
                            <span>🧺 Laundry</span>
                            <strong>${apartment.laundry_score}</strong>
                        </div>
                    ` : ''}
                    ${apartment.space_luxury_score !== undefined ? `
                        <div style="display: flex; justify-content: space-between; padding: 8px; background: #f5f5f7; border-radius: 6px;">
                            <span>📐 Space & Luxury</span>
                            <strong>${apartment.space_luxury_score}</strong>
                        </div>
                    ` : ''}
                </div>
            </div>
            
            <div class="key-details" style="margin-top: 20px;">
                <h4>Key Details</h4>
                <div style="display: grid; gap: 8px; font-size: 14px;">
                    <div><strong>Price:</strong> $${apartment.price || 'N/A'}</div>
                    <div><strong>Bedrooms:</strong> ${apartment.bedrooms || 'N/A'}</div>
                    <div><strong>Bathrooms:</strong> ${apartment.bathrooms || 'N/A'}</div>
                    <div><strong>Square Feet:</strong> ${apartment.sqft || 'N/A'}</div>
                    <div><strong>Commute (You):</strong> ${apartment.commute_you || 'N/A'} min</div>
                    <div><strong>Commute (Partner):</strong> ${apartment.commute_partner || 'N/A'} min</div>
                </div>
            </div>
            
            <div style="margin-top: 16px; text-align: center;">
                <button class="btn btn-primary" onclick="window.open('/','_blank').focus(); setTimeout(() => {
                    const selector = document.querySelector('#apartment_selector');
                    if (selector) {
                        selector.value = '${apartment.row}';
                        loadSelectedApartment();
                    }
                }, 1000)">
                    📝 Open in Editor
                </button>
            </div>
        </div>
    `;
}

function closePrefDetailModal() {
    document.getElementById('prefDetailModal').classList.add('hidden');
}

// ================== INITIALIZATION ==================

// Initialize when preferences tab is first shown
document.addEventListener('DOMContentLoaded', function() {
    // Check if preferences tab exists
    if (document.getElementById('preferencesTab')) {
        // Pre-load profiles when page loads
        setTimeout(() => {
            if (document.getElementById('prefProfilesSection')?.classList.contains('active')) {
                loadProfiles();
            }
        }, 500);
    }
});



