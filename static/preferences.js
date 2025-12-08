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

// ================== PROFILE COMPARISON ==================

let cachedFullProfiles = []; // Store full profile data for comparison

async function compareProfiles() {
    if (cachedProfiles.length < 2) {
        alert('You need at least 2 profiles to compare. Create another profile first.');
        return;
    }
    
    document.getElementById('profileCompareModal').classList.remove('hidden');
    document.getElementById('profileCompareContent').innerHTML = '<div class="loading-spinner">Loading comparison...</div>';
    
    // Fetch full profile data for each profile
    try {
        const fullProfiles = [];
        for (const profileSummary of cachedProfiles) {
            const response = await fetch(`/preferences/api/profiles/${encodeURIComponent(profileSummary.name)}`);
            const data = await response.json();
            if (data.success && data.profile) {
                fullProfiles.push(data.profile);
            }
        }
        
        cachedFullProfiles = fullProfiles;
        
        if (fullProfiles.length < 2) {
            document.getElementById('profileCompareContent').innerHTML = '<p class="error">Could not load profile data for comparison.</p>';
            return;
        }
        
        // Build comparison content
        const html = buildProfileComparisonHTML(fullProfiles);
        document.getElementById('profileCompareContent').innerHTML = html;
    } catch (error) {
        console.error('Error loading profiles for comparison:', error);
        document.getElementById('profileCompareContent').innerHTML = `<p class="error">Error: ${error.message}</p>`;
    }
}

function closeProfileCompare() {
    document.getElementById('profileCompareModal').classList.add('hidden');
}

function buildProfileComparisonHTML(profiles) {
    const profileColors = {
        0: { bg: '#0066cc', light: '#e8f4ff' },
        1: { bg: '#9c27b0', light: '#f3e5f5' },
        2: { bg: '#ff9500', light: '#fff8e1' },
        3: { bg: '#34c759', light: '#e8f5e9' },
    };
    
    let html = '';
    
    // Profile summary cards
    html += '<div class="profile-compare-header">';
    profiles.forEach((profile, index) => {
        const colors = profileColors[index % Object.keys(profileColors).length];
        
        const criteriaCount = profile.criteria?.length || 0;
        // Sort criteria by priority to find top priority
        const sortedCriteria = [...(profile.criteria || [])].sort((a, b) => a.priority_order - b.priority_order);
        const topPriority = sortedCriteria[0]?.display_name || 'N/A';
        
        html += `
            <div class="profile-compare-card" style="border-top: 4px solid ${colors.bg};">
                <h4 style="color: ${colors.bg};">${profile.person_name}</h4>
                <div class="profile-stats">
                    <div>${criteriaCount} criteria</div>
                    <div>Top priority: <strong>${topPriority}</strong></div>
                </div>
            </div>
        `;
    });
    html += '</div>';
    
    // Collect all unique criteria across profiles
    const allCriteria = new Map();
    profiles.forEach(profile => {
        (profile.criteria || []).forEach(criterion => {
            if (!allCriteria.has(criterion.id)) {
                allCriteria.set(criterion.id, {
                    id: criterion.id,
                    display_name: criterion.display_name,
                    profiles: {}
                });
            }
            allCriteria.get(criterion.id).profiles[profile.person_name] = criterion;
        });
    });
    
    // Sort by average priority
    const sortedCriteria = Array.from(allCriteria.values()).sort((a, b) => {
        const avgA = Object.values(a.profiles).reduce((sum, p) => sum + (p.priority_order || 99), 0) / Object.keys(a.profiles).length;
        const avgB = Object.values(b.profiles).reduce((sum, p) => sum + (p.priority_order || 99), 0) / Object.keys(b.profiles).length;
        return avgA - avgB;
    });
    
    // Build criteria comparison using stacked sliders (same format as apartment evaluation)
    html += '<div class="criteria-sliders-container">';
    
    sortedCriteria.forEach(criterionData => {
        html += buildComparisonCriterionSliderRow(criterionData, profiles, profileColors);
    });
    
    html += '</div>';
    
    return html;
}

function buildComparisonCriterionSliderRow(criterionData, profiles, profileColors) {
    const icon = getCriterionIcon(criterionData.id);
    
    // Build threshold info for visualization
    const criterionInfo = {
        display_name: criterionData.display_name,
        profiles: {}
    };
    
    let isLowerBetter = true;
    
    profiles.forEach(profile => {
        const criterion = criterionData.profiles[profile.person_name];
        if (criterion) {
            const op = criterion.ideal?.[0]?.operator || 'lte';
            isLowerBetter = op === 'lte' || op === 'lt';
            
            criterionInfo.profiles[profile.person_name] = {
                ideal: criterion.ideal?.[0]?.value,
                acceptable: criterion.acceptable?.[0]?.value,
                veto: criterion.veto?.[0]?.value,
                is_lower_better: isLowerBetter,
                priority_order: criterion.priority_order,
            };
        }
    });
    
    criterionInfo.is_lower_better = isLowerBetter;
    
    // Calculate unified bounds
    const unifiedBounds = calculateComparisonBounds(criterionInfo, profiles.map(p => p.person_name));
    
    let html = `
        <div class="criterion-slider-row">
            <div class="criterion-slider-header">
                <div class="criterion-slider-title">
                    ${icon} ${criterionData.display_name}
                </div>
            </div>
            
            <div class="slider-profiles-stack">
    `;
    
    // Build stacked sliders for each profile
    profiles.forEach((profile, index) => {
        const profileData = criterionInfo.profiles[profile.person_name];
        if (!profileData) return;
        
        const colors = profileColors[index % Object.keys(profileColors).length];
        const priority = profileData.priority_order;
        
        html += `
            <div class="profile-slider-container">
                <div class="profile-slider-label" style="color: ${colors.bg};">
                    ${profile.person_name}
                    <span style="margin-left: 8px; font-size: 10px; color: #666; font-weight: normal;">#${priority}</span>
                </div>
                ${buildComparisonProfileSlider(profileData, colors, unifiedBounds, criterionData.id)}
            </div>
        `;
    });
    
    // Scale labels
    const minLabel = formatCompareThreshold(criterionData.id, unifiedBounds.minVal);
    const maxLabel = formatCompareThreshold(criterionData.id, unifiedBounds.maxVal);
    html += `
            <div class="scale-labels">
                <span class="scale-label min-label">${minLabel}</span>
                <span class="scale-label max-label">${maxLabel}</span>
            </div>
        </div>
        
        <div class="criterion-details-panel">
            <div class="criterion-details-grid">
                ${buildComparisonThresholdDetails(criterionData, profiles, profileColors)}
            </div>
        </div>
    </div>
    `;
    
    return html;
}

function calculateComparisonBounds(criterionInfo, profileNames) {
    let allThresholds = [];
    let isLowerBetter = criterionInfo.is_lower_better;
    
    profileNames.forEach(profileName => {
        const profileData = criterionInfo.profiles[profileName];
        if (!profileData) return;
        
        if (profileData.ideal != null) allThresholds.push(profileData.ideal);
        if (profileData.acceptable != null) allThresholds.push(profileData.acceptable);
        if (profileData.veto != null) allThresholds.push(profileData.veto);
    });
    
    if (allThresholds.length === 0) {
        return { minVal: 0, maxVal: 10, isLowerBetter };
    }
    
    const minThreshold = Math.min(...allThresholds);
    const maxThreshold = Math.max(...allThresholds);
    
    const range = maxThreshold - minThreshold;
    const padding = Math.max(3, range * 0.15);
    
    return {
        minVal: Math.max(0, minThreshold - padding),
        maxVal: maxThreshold + padding,
        isLowerBetter
    };
}

function buildComparisonProfileSlider(profileData, colors, unifiedBounds, criterionId) {
    const { ideal, acceptable, veto, is_lower_better } = profileData;
    const { minVal, maxVal } = unifiedBounds;
    
    const range = maxVal - minVal;
    
    const toPercent = (val) => {
        if (val == null) return null;
        return Math.max(0, Math.min(100, ((val - minVal) / range) * 100));
    };
    
    // Calculate zone positions
    let idealStart, idealEnd, acceptableStart, acceptableEnd, vetoStart, vetoEnd;
    
    if (is_lower_better) {
        const idealVal = ideal != null ? ideal : minVal;
        const vetoBound = veto != null ? veto : (acceptable != null ? acceptable : idealVal);
        idealStart = 0;
        idealEnd = toPercent(idealVal);
        acceptableStart = idealEnd;
        acceptableEnd = toPercent(vetoBound);
        vetoStart = acceptableEnd;
        vetoEnd = 100;
    } else {
        const idealVal = ideal != null ? ideal : maxVal;
        const vetoBound = veto != null ? veto : (acceptable != null ? acceptable : idealVal);
        vetoStart = 0;
        vetoEnd = toPercent(vetoBound);
        acceptableStart = vetoEnd;
        acceptableEnd = toPercent(idealVal);
        idealStart = acceptableEnd;
        idealEnd = 100;
    }
    
    return `
        <div class="profile-slider">
            <!-- Ideal zone -->
            <div class="slider-zone ideal" style="left: ${idealStart}%; width: ${Math.max(0, idealEnd - idealStart)}%;">
                ${Math.max(0, idealEnd - idealStart) > 5 ? '<span class="slider-zone-label">Ideal</span>' : ''}
            </div>
            <!-- Acceptable zone -->
            <div class="slider-zone acceptable" style="left: ${acceptableStart}%; width: ${Math.max(0, acceptableEnd - acceptableStart)}%;">
                ${Math.max(0, acceptableEnd - acceptableStart) > 5 ? '<span class="slider-zone-label">OK</span>' : ''}
            </div>
            <!-- Veto zone -->
            <div class="slider-zone veto" style="left: ${vetoStart}%; width: ${Math.max(0, vetoEnd - vetoStart)}%;">
                ${Math.max(0, vetoEnd - vetoStart) > 5 ? '<span class="slider-zone-label">Veto</span>' : ''}
            </div>
        </div>
    `;
}

function buildComparisonThresholdDetails(criterionData, profiles, profileColors) {
    let html = '';
    
    profiles.forEach((profile, index) => {
        const criterion = criterionData.profiles[profile.person_name];
        const colors = profileColors[index % Object.keys(profileColors).length];
        
        if (criterion) {
            const ideal = criterion.ideal?.[0]?.value;
            const acceptable = criterion.acceptable?.[0]?.value;
            const veto = criterion.veto?.[0]?.value;
            
            html += `
                <div class="criterion-detail-card" style="border-left: 3px solid ${colors.bg};">
                    <h6 style="color: ${colors.bg};">${profile.person_name}</h6>
                    <div class="threshold-display">
                        <div class="threshold-row">
                            <span class="threshold-tier-label ideal">Ideal</span>
                            <span class="threshold-value">${formatCompareThreshold(criterionData.id, ideal)}</span>
                        </div>
                        <div class="threshold-row">
                            <span class="threshold-tier-label acceptable">OK</span>
                            <span class="threshold-value">${formatCompareThreshold(criterionData.id, acceptable)}</span>
                        </div>
                        <div class="threshold-row">
                            <span class="threshold-tier-label veto">Veto</span>
                            <span class="threshold-value">${formatCompareThreshold(criterionData.id, veto)}</span>
                        </div>
                    </div>
                </div>
            `;
        } else {
            html += `
                <div class="criterion-detail-card" style="border-left: 3px solid #ccc; opacity: 0.6;">
                    <h6 style="color: #999;">${profile.person_name}</h6>
                    <div style="color: #999; font-size: 13px; padding: 8px 0;">Not configured</div>
                </div>
            `;
        }
    });
    
    return html;
}

function formatCompareThreshold(criterionId, value) {
    if (value == null || value === undefined) return 'N/A';
    
    const formats = {
        'commute': v => `${Math.round(v)} min`,
        'price': v => `$${Math.round(v).toLocaleString()}`,
        'gym': v => `${Math.round(v)} min`,
        'safety': v => `${v}/10`,
        'wfh_quality': v => `${v}/10`,
        'parking': v => `${v}/10`,
        'laundry': v => `${v}/10`,
        'happening': v => `${v}/10`,
        'space_luxury': v => `${Math.round(v)} sqft`,
    };
    
    const formatter = formats[criterionId] || (v => v);
    return formatter(value);
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

// Store cached threshold data for slider visualization
let cachedThresholdData = null;
let cachedApartmentValues = null;

async function showEvalDetail(apartmentId) {
    const eval_ = cachedApartments.find(e => e.apartment_id === apartmentId);
    if (!eval_) return;
    
    document.getElementById('prefDetailTitle').textContent = `Evaluation: ${apartmentId}`;
    
    // Show loading state
    document.getElementById('prefDetailContent').innerHTML = '<div class="loading-spinner">Loading evaluation details...</div>';
    document.getElementById('prefDetailModal').classList.remove('hidden');
    
    // Get selected profile names
    const checkboxes = document.querySelectorAll('#evalProfileCheckboxes input[type="checkbox"]:checked');
    const profileNames = Array.from(checkboxes).map(cb => cb.value);
    
    // Load apartment data from analysis endpoint for the Analysis tab display (not for backend)
    let analysisApartment = null;
    try {
        const response = await fetch('/get_analysis_data');
        const data = await response.json();
        
        if (data.success) {
            analysisApartment = data.comparison.find(apt => apt.address === apartmentId) || null;
        }
    } catch (error) {
        console.error('Error loading apartment analysis:', error);
    }
    
    // We intentionally pass an empty payload so the backend loads the full row from Sheets,
    // ensuring commute/gym and other fields are present.
    const apartmentPayload = {};
    
    // Load threshold data from the detail endpoint
    try {
        const detailResponse = await fetch(`/preferences/api/apartment/${encodeURIComponent(apartmentId)}/detail`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                profiles: profileNames,
                apartment: apartmentPayload
            }),
        });
        
        const detailData = await detailResponse.json();
        
        if (detailData.success) {
            cachedThresholdData = detailData.threshold_data;
            cachedApartmentValues = detailData.apartment_values;
        }
    } catch (error) {
        console.error('Error loading threshold data:', error);
    }
    
    // Build side-by-side layout
    let html = `<div class="eval-detail-split-view">`;
    
    // LEFT PANEL: Preference Evaluation
    html += `<div class="eval-detail-panel eval-panel-left">
        <div class="eval-panel-header">
            <h4>📊 Preference Evaluation</h4>
        </div>
        <div class="eval-panel-content">`;
    
    // Summary scores per person at the top
    html += '<div class="eval-summary-cards" style="display: flex; gap: 12px; margin-bottom: 16px; flex-wrap: wrap;">';
    for (const [personName, individual] of Object.entries(eval_.individual_evaluations)) {
        const scoreColor = individual.veto_count > 0 ? '#dc3545' : '#34c759';
        html += `
            <div class="eval-summary-card" style="flex: 1; min-width: 140px; background: #f8f9fa; border-radius: 10px; padding: 12px; border-left: 4px solid ${scoreColor};">
                <div style="font-weight: 600; margin-bottom: 6px; font-size: 13px;">${personName}</div>
                <div style="font-size: 24px; font-weight: 700; color: ${scoreColor};">${(individual.tie_break_score * 100).toFixed(0)}%</div>
                <div style="font-size: 11px; color: #666; margin-top: 4px;">
                    <span style="color: #34c759;">✓${individual.ideal_count}</span> | 
                    <span style="color: #ff9500;">~${individual.acceptable_count}</span> | 
                    <span style="color: #dc3545;">✗${individual.veto_count}</span>
                </div>
            </div>
        `;
    }
    html += '</div>';
    
    // Build the criteria sliders visualization
    html += buildCriteriaSliderVisualization(eval_, cachedThresholdData, cachedApartmentValues);
    
    // Disagreements section
    if (eval_.disagreements && eval_.disagreements.length > 0) {
        html += `
            <div class="detail-section" style="margin-top: 16px; background: #fff3cd; padding: 12px; border-radius: 8px;">
                <h5 style="margin: 0 0 10px 0; font-size: 14px;">⚠️ Areas of Disagreement</h5>
                ${eval_.disagreements.map(d => `
                    <div style="margin-bottom: 6px; font-size: 13px;">
                        <strong>${d.criterion_id}:</strong> 
                        ${Object.entries(d.tiers_by_person).map(([p, t]) => `
                            <span class="tier-result-badge ${t}">${p}: ${t}</span>
                        `).join(' ')}
                    </div>
                `).join('')}
            </div>
        `;
    }
    
    html += '</div></div>'; // Close panel content and left panel
    
    // RIGHT PANEL: Apartment Analysis
    html += `<div class="eval-detail-panel eval-panel-right">
        <div class="eval-panel-header">
            <h4>🏠 Apartment Analysis</h4>
        </div>
        <div class="eval-panel-content">`;
    
    if (analysisApartment) {
        html += buildApartmentAnalysisHTML(analysisApartment);
    } else {
        html += '<p style="color: #666; padding: 20px; text-align: center;">Apartment details not found. Run analysis to see detailed scores.</p>';
    }
    
    html += '</div></div>'; // Close panel content and right panel
    html += '</div>'; // Close split view
    
    document.getElementById('prefDetailContent').innerHTML = html;
}

/**
 * Build the slider visualization for all criteria
 */
function buildCriteriaSliderVisualization(eval_, thresholdData, apartmentValues) {
    if (!thresholdData) {
        return '<p class="error">Threshold data not available for visualization.</p>';
    }
    
    const profileNames = Object.keys(eval_.individual_evaluations);
    const profileColors = {
        0: { bg: '#0066cc', light: '#e8f4ff' },
        1: { bg: '#9c27b0', light: '#f3e5f5' },
        2: { bg: '#ff9500', light: '#fff8e1' },
    };
    
    let html = '<div class="criteria-sliders-container">';
    
    // Sort criteria by display name
    const sortedCriteria = Object.entries(thresholdData).sort((a, b) => 
        (a[1].display_name || a[0]).localeCompare(b[1].display_name || b[0])
    );
    
    for (const [criterionId, criterionInfo] of sortedCriteria) {
        // Get the actual value for this criterion
        const actualValue = getActualValueForCriterion(criterionId, criterionInfo, apartmentValues);
        const isLowerBetter = criterionInfo.is_lower_better;
        
        // Get tier results from each profile
        const tierResults = {};
        for (const [personName, individual] of Object.entries(eval_.individual_evaluations)) {
            tierResults[personName] = individual.tier_results[criterionId] || 'unknown';
        }
        
        html += `
            <div class="criterion-slider-row">
                <div class="criterion-slider-header">
                    <div class="criterion-slider-title">
                        ${getCriterionIcon(criterionId)} ${criterionInfo.display_name || criterionId}
                    </div>
                    ${actualValue !== null ? `
                        <div class="criterion-actual-value">${formatActualValue(criterionId, actualValue)}</div>
                    ` : ''}
                </div>
                
                <div class="slider-profiles-stack">
                    ${buildStackedSliders(criterionId, criterionInfo, profileNames, profileColors, actualValue, tierResults)}
                </div>
                
                <div class="criterion-details-panel">
                    <div class="criterion-details-grid">
                        ${buildThresholdDetails(criterionId, criterionInfo, profileNames, tierResults, actualValue)}
                    </div>
                </div>
            </div>
        `;
    }
    
    html += '</div>';
    return html;
}

/**
 * Build stacked horizontal sliders for all profiles with unified bounds
 */
function buildStackedSliders(criterionId, criterionInfo, profileNames, profileColors, actualValue, tierResults) {
    // For commute criterion, use profile-specific actual values for bounds calculation
    let adjustedActualValue = actualValue;
    if (criterionId === 'commute') {
        // Collect all profile-specific commute values for bounds
        const commuteValues = [];
        profileNames.forEach(profileName => {
            const profileData = criterionInfo.profiles[profileName];
            if (profileData && profileData.actual_value !== null && profileData.actual_value !== undefined) {
                commuteValues.push(profileData.actual_value);
            }
        });
        // Use null for unified actualValue since each profile has its own
        adjustedActualValue = commuteValues.length > 0 ? null : actualValue;
    }
    
    // Calculate unified bounds across all profiles (includes profile-specific actual values)
    const unifiedBounds = calculateUnifiedBounds(criterionInfo, profileNames, adjustedActualValue);
    
    let html = '';
    
    // For commute, show each profile's commute time separately
    if (criterionId === 'commute') {
        // Build a header showing all profile commute times
        const commuteInfoParts = [];
        profileNames.forEach(profileName => {
            const profileData = criterionInfo.profiles[profileName];
            if (profileData && profileData.actual_value !== null && profileData.actual_value !== undefined) {
                const modeIcon = profileData.commute_mode === 'transit' ? '🚇' : '🚗';
                commuteInfoParts.push(`<span style="margin-right: 12px;">${modeIcon} <strong>${profileName}:</strong> ${profileData.actual_value} min</span>`);
            }
        });
        if (commuteInfoParts.length > 0) {
            html += `<div class="actual-value-indicator" style="text-align: center; margin-bottom: 8px; font-size: 13px; font-weight: 600; color: #1d1d1f; background: #f0f8ff; padding: 6px; border-radius: 4px; border: 1px solid #d0e0f0;">
                ${commuteInfoParts.join('')}
            </div>`;
        }
    } else if (actualValue !== null) {
        html += `<div class="actual-value-indicator" style="text-align: center; margin-bottom: 8px; font-size: 13px; font-weight: 600; color: #1d1d1f; background: #f0f8ff; padding: 6px; border-radius: 4px; border: 1px solid #d0e0f0;">
            <strong>Actual:</strong> ${formatActualValue(criterionId, actualValue)}
        </div>`;
    }
    
    profileNames.forEach((profileName, index) => {
        const profileData = criterionInfo.profiles[profileName];
        if (!profileData) return;
        
        // For commute, use profile-specific actual value
        const profileActualValue = (criterionId === 'commute' && profileData.actual_value !== undefined)
            ? profileData.actual_value
            : actualValue;
        
        const colors = profileColors[index % Object.keys(profileColors).length];
        // Prefer server tier result; if missing or unknown, compute locally to avoid mismatches
        const tier = tierResults[profileName] && tierResults[profileName] !== 'unknown'
            ? tierResults[profileName]
            : computeTierFromThresholds(profileData, profileActualValue);
        
        // Pass unified bounds to the slider builder with profile-specific actual value
        const sliderHtml = buildSingleProfileSlider(profileData, profileActualValue, colors, tier, profileName, unifiedBounds);
        
        html += `
            <div class="profile-slider-container">
                <div class="profile-slider-label" style="color: ${colors.bg};">
                    ${profileName} 
                    <span class="tier-result-badge ${tier}" style="margin-left: 8px; font-size: 10px;">${tier.toUpperCase()}</span>
                </div>
                ${sliderHtml}
            </div>
        `;
    });

    // Min/Max scale labels for the unified bounds
    const minLabel = formatThresholdValue(criterionId, unifiedBounds.minVal);
    const maxLabel = formatThresholdValue(criterionId, unifiedBounds.maxVal);
    html += `
        <div class="scale-labels">
            <span class="scale-label min-label">${minLabel}</span>
            <span class="scale-label max-label">${maxLabel}</span>
        </div>
    `;
    
    return html;
}

/**
 * Calculate unified min/max bounds across all profiles for consistent slider positioning
 */
function calculateUnifiedBounds(criterionInfo, profileNames, actualValue) {
    let allThresholds = [];
    let isLowerBetter = true;
    
    // Collect all threshold values from all profiles
    profileNames.forEach(profileName => {
        const profileData = criterionInfo.profiles[profileName];
        if (!profileData) return;
        
        isLowerBetter = profileData.is_lower_better;
        
        if (profileData.ideal !== null && profileData.ideal !== undefined) {
            allThresholds.push(profileData.ideal);
        }
        if (profileData.acceptable !== null && profileData.acceptable !== undefined) {
            allThresholds.push(profileData.acceptable);
        }
        if (profileData.veto !== null && profileData.veto !== undefined) {
            allThresholds.push(profileData.veto);
        }
        
        // Include profile-specific actual value (e.g., for commute)
        if (profileData.actual_value !== null && profileData.actual_value !== undefined) {
            allThresholds.push(profileData.actual_value);
        }
    });
    
    // Include shared actual value in bounds calculation
    if (actualValue !== null && actualValue !== undefined) {
        allThresholds.push(actualValue);
    }
    
    if (allThresholds.length === 0) {
        return { minVal: 0, maxVal: 10, isLowerBetter };
    }
    
    const minThreshold = Math.min(...allThresholds);
    const maxThreshold = Math.max(...allThresholds);
    
    // Add padding (3 units or 10% of range, whichever is larger)
    const range = maxThreshold - minThreshold;
    const padding = Math.max(3, range * 0.1);
    
    let minVal, maxVal;
    if (isLowerBetter) {
        // For lower-is-better: start from 0 or slightly below min, extend past max veto
        minVal = Math.max(0, minThreshold - padding);
        maxVal = maxThreshold + padding;
    } else {
        // For higher-is-better: start below veto, extend past ideal
        minVal = Math.max(0, minThreshold - padding);
        maxVal = maxThreshold + padding;
    }
    
    // Ensure we have a reasonable range
    if (maxVal <= minVal) {
        maxVal = minVal + 10;
    }
    
    return { minVal, maxVal, isLowerBetter };
}

/**
 * Build a single profile's slider with zones using unified bounds
 */
function buildSingleProfileSlider(profileData, actualValue, colors, tier, profileName, unifiedBounds) {
    const { ideal, acceptable, veto, is_lower_better } = profileData;
    const { minVal, maxVal } = unifiedBounds;
    
    const range = maxVal - minVal;
    
    // Helper to convert a value to percentage position
    const toPercent = (val) => {
        if (val === null || val === undefined) return null;
        return Math.max(0, Math.min(100, ((val - minVal) / range) * 100));
    };
    
    // Calculate zone positions as percentages (robust to missing thresholds)
    let idealStart, idealEnd, acceptableStart, acceptableEnd, vetoStart, vetoEnd;
    if (is_lower_better) {
        // Lower is better:
        // ideal: min -> ideal
        // acceptable: ideal -> (veto if present else acceptable if present else ideal)
        // veto: acceptable_end -> max
        const idealVal = ideal !== null ? ideal : minVal;
        const vetoBound = (veto !== null ? veto : (acceptable !== null ? acceptable : idealVal));
        idealStart = 0;
        idealEnd = toPercent(idealVal);
        acceptableStart = idealEnd;
        acceptableEnd = toPercent(vetoBound);
        vetoStart = acceptableEnd;
        vetoEnd = 100;
    } else {
        // Higher is better:
        // veto: min -> veto
        // acceptable: veto -> ideal
        // ideal: ideal -> max
        const idealVal = ideal !== null ? ideal : maxVal;
        const vetoBound = (veto !== null ? veto : (acceptable !== null ? acceptable : idealVal));
        vetoStart = 0;
        vetoEnd = toPercent(vetoBound);
        acceptableStart = vetoEnd;
        acceptableEnd = toPercent(idealVal);
        idealStart = acceptableEnd;
        idealEnd = 100;
    }
    
    // Calculate actual value position using the same unified bounds
    const actualPosition = actualValue !== null ? toPercent(actualValue) : null;
    
    // Check if we should show the actual line
    const hasActualLine = actualPosition !== null && actualPosition >= 0 && actualPosition <= 100;
    
    return `
        <div class="profile-slider">
            <!-- Ideal zone -->
            <div class="slider-zone ideal" style="left: ${idealStart}%; width: ${Math.max(0, idealEnd - idealStart)}%;">
                ${Math.max(0, idealEnd - idealStart) > 1 ? '<span class="slider-zone-label">Ideal</span>' : ''}
            </div>
            <!-- Acceptable zone -->
            <div class="slider-zone acceptable" style="left: ${acceptableStart}%; width: ${Math.max(0, acceptableEnd - acceptableStart)}%;">
                ${Math.max(0, acceptableEnd - acceptableStart) > 1 ? '<span class="slider-zone-label">OK</span>' : ''}
            </div>
            <!-- Veto zone -->
            <div class="slider-zone veto" style="left: ${vetoStart}%; width: ${Math.max(0, vetoEnd - vetoStart)}%;">
                ${Math.max(0, vetoEnd - vetoStart) > 1 ? '<span class="slider-zone-label">Veto</span>' : ''}
            </div>
            
            <!-- Actual value line - rendered on top of zones -->
            ${hasActualLine ? `
                <div class="score-line-container" style="left: ${actualPosition}%; position: absolute; top: -4px; bottom: -4px; z-index: 100;">
                    <div class="score-line" style="width: 4px; height: 100%; background: #000; border-radius: 2px;"></div>
                    <div class="score-line-marker" style="position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); width: 14px; height: 14px; background: #000; border: 3px solid #fff; border-radius: 50%; box-shadow: 0 2px 6px rgba(0,0,0,0.5);"></div>
                </div>
            ` : ''}
        </div>
    `;
}

/**
 * Build threshold details for a criterion
 */
function buildThresholdDetails(criterionId, criterionInfo, profileNames, tierResults, actualValue) {
    let html = '';
    
    profileNames.forEach(profileName => {
        const profileData = criterionInfo.profiles[profileName];
        if (!profileData) return;
        
        const tier = tierResults[profileName];
        const { ideal, acceptable, veto, is_lower_better } = profileData;
        
        // For commute, use profile-specific actual value
        const profileActualValue = (criterionId === 'commute' && profileData.actual_value !== undefined) 
            ? profileData.actual_value 
            : actualValue;
        
        // Calculate distance from thresholds
        let distanceInfo = '';
        if (profileActualValue !== null && profileActualValue !== undefined) {
            if (tier === 'ideal') {
                const margin = is_lower_better ? (ideal - profileActualValue) : (profileActualValue - ideal);
                distanceInfo = `<span class="distance-indicator positive">+${Math.abs(margin).toFixed(1)} margin</span>`;
            } else if (tier === 'acceptable') {
                const toIdeal = is_lower_better ? (profileActualValue - ideal) : (ideal - profileActualValue);
                distanceInfo = `<span class="distance-indicator negative">${toIdeal.toFixed(1)} from ideal</span>`;
            } else if (tier === 'veto') {
                const pastVeto = is_lower_better ? (profileActualValue - veto) : (veto - profileActualValue);
                distanceInfo = `<span class="distance-indicator negative">${Math.abs(pastVeto).toFixed(1)} past veto</span>`;
            }
        }
        
        // Calculate percentage in range
        let percentageBar = '';
        if (profileActualValue !== null && profileActualValue !== undefined && ideal !== null) {
            const range = is_lower_better ? ideal : (ideal - (veto || 0));
            const position = is_lower_better ? profileActualValue : (profileActualValue - (veto || 0));
            const percentage = Math.max(0, Math.min(100, ((range - position) / range) * 100));
            
            percentageBar = `
                <div class="score-percentage-bar">
                    <div class="score-percentage-fill ${tier}" style="width: ${percentage}%;"></div>
                </div>
            `;
        }
        
        // Build commute-specific extra info
        let commuteExtras = '';
        if (criterionId === 'commute' && profileData.commute_mode) {
            const modeIcon = profileData.commute_mode === 'transit' ? '🚇' : '🚗';
            const modeLabel = profileData.commute_mode === 'transit' ? 'Transit' : 'Driving';
            
            commuteExtras = `
                <div class="commute-extras" style="margin-top: 8px; padding: 8px; background: #f8f9fa; border-radius: 6px; font-size: 12px;">
                    <div style="display: flex; align-items: center; gap: 6px; margin-bottom: 4px;">
                        <span>${modeIcon}</span>
                        <strong>${modeLabel}</strong>
                        ${profileActualValue !== null ? `<span style="margin-left: auto;">${profileActualValue} min</span>` : ''}
                    </div>
            `;
            
            // Annoyingness score
            if (profileData.annoyingness_score !== null && profileData.annoyingness_score !== undefined) {
                const annoyScore = parseFloat(profileData.annoyingness_score).toFixed(1);
                const annoyColor = annoyScore >= 7 ? '#34c759' : (annoyScore >= 4 ? '#ff9500' : '#ff3b30');
                commuteExtras += `
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <span style="color: #666;">Route Quality:</span>
                        <span style="color: ${annoyColor}; font-weight: 600;">${annoyScore}/10</span>
                    </div>
                `;
            }
            
            // Transit-specific details
            if (profileData.commute_mode === 'transit') {
                if (profileData.transit_walking_mins !== null && profileData.transit_walking_mins !== undefined) {
                    commuteExtras += `
                        <div style="display: flex; justify-content: space-between;">
                            <span style="color: #666;">🚶 Walking:</span>
                            <span>${profileData.transit_walking_mins} min</span>
                        </div>
                    `;
                }
                if (profileData.transit_transfers !== null && profileData.transit_transfers !== undefined) {
                    commuteExtras += `
                        <div style="display: flex; justify-content: space-between;">
                            <span style="color: #666;">🔄 Transfers:</span>
                            <span>${profileData.transit_transfers}</span>
                        </div>
                    `;
                }
            }
            
            commuteExtras += '</div>';
        }
        
        html += `
            <div class="criterion-detail-card">
                <h6>${profileName}</h6>
                <div class="threshold-display">
                    <div class="threshold-row">
                        <span class="threshold-tier-label ideal">Ideal</span>
                        <span class="threshold-value">${ideal !== null ? formatThresholdValue(criterionId, ideal) : 'N/A'}</span>
                    </div>
                    <div class="threshold-row">
                        <span class="threshold-tier-label acceptable">OK</span>
                        <span class="threshold-value">${acceptable !== null ? formatThresholdValue(criterionId, acceptable) : 'N/A'}</span>
                    </div>
                    <div class="threshold-row">
                        <span class="threshold-tier-label veto">Veto</span>
                        <span class="threshold-value">${veto !== null ? formatThresholdValue(criterionId, veto) : 'N/A'}</span>
                    </div>
                </div>
                ${distanceInfo}
                ${percentageBar}
                ${commuteExtras}
            </div>
        `;
    });
    
    return html;
}

/**
 * Get actual value for a criterion from apartment data
 */
function getActualValueForCriterion(criterionId, criterionInfo, apartmentValues) {
    // Map criterion IDs to apartment value keys
    const fieldMapping = {
        'commute': 'commute_duration',
        'price': 'total_monthly_cost',
        'safety': 'safety_score',
        'wfh_quality': 'wfh_score',
        'gym': 'gym_walk_time',
        'parking': 'parking_score',
        'laundry': 'laundry_score',
        'happening': 'happening_score',
        'space_luxury': 'sqft',
    };
    
    // First: Try to get from apartment values (most reliable)
    const field = fieldMapping[criterionId] || criterionInfo?.field;
    if (field && apartmentValues && apartmentValues[field]) {
        const val = apartmentValues[field];
        const result = typeof val === 'object' ? val.value : val;
        if (result !== null && result !== undefined) {
            return result;
        }
    }
    
    // Second: Try to get actual_value from threshold data profiles
    if (criterionInfo && criterionInfo.profiles) {
        for (const profileData of Object.values(criterionInfo.profiles)) {
            if (profileData && profileData.actual_value !== null && profileData.actual_value !== undefined) {
                return profileData.actual_value;
            }
        }
    }
    
    return null;
}

/**
 * Fallback: compute tier locally from thresholds and actual value
 */
function computeTierFromThresholds(profileData, actualValue) {
    if (actualValue === null || actualValue === undefined || !profileData) return 'unknown';
    const { ideal, acceptable, veto, is_lower_better } = profileData;
    if (is_lower_better) {
        if (ideal !== null && actualValue <= ideal) return 'ideal';
        // If a veto bound exists, acceptable should extend up to veto
        if (veto !== null && actualValue <= veto) return 'acceptable';
        if (acceptable !== null && actualValue <= acceptable) return 'acceptable';
        return 'veto';
    } else {
        if (ideal !== null && actualValue >= ideal) return 'ideal';
        if (veto !== null && actualValue >= veto) return 'acceptable';
        if (acceptable !== null && actualValue >= acceptable) return 'acceptable';
        return 'veto';
    }
}

/**
 * Format actual value for display
 */
function formatActualValue(criterionId, value) {
    const formats = {
        'commute': v => `${v} min`,
        'price': v => `$${Math.round(v).toLocaleString()}`,
        'gym': v => `${v} min walk`,
        'safety': v => `${v}/10`,
        'wfh_quality': v => `${v}/10`,
        'parking': v => `${v}/10`,
        'laundry': v => `${v}/10`,
        'happening': v => `${v}/10`,
        'space_luxury': v => `${v} sqft`,
    };
    
    const formatter = formats[criterionId] || (v => v);
    return formatter(value);
}

/**
 * Format threshold value for display
 */
function formatThresholdValue(criterionId, value) {
    return formatActualValue(criterionId, value);
}

/**
 * Get icon for a criterion
 */
function getCriterionIcon(criterionId) {
    const icons = {
        'safety': '🛡️',
        'commute': '🚗',
        'wfh_quality': '💻',
        'parking': '🅿️',
        'gym': '💪',
        'space_luxury': '🏠',
        'laundry': '👕',
        'happening': '🎉',
        'price': '💰',
    };
    return icons[criterionId] || '📊';
}

function switchEvalDetailTab(tabName) {
    // Update tab buttons
    document.querySelectorAll('.eval-detail-tab').forEach(tab => {
        tab.classList.remove('active');
    });
    event.target.classList.add('active');
    
    // Update content - use 'active' class not 'hidden'
    document.querySelectorAll('.eval-detail-content').forEach(content => {
        content.classList.remove('active');
    });
    document.getElementById(`evalDetail${tabName.charAt(0).toUpperCase() + tabName.slice(1)}`).classList.add('active');
}

function buildApartmentAnalysisHTML(apartment) {
    // Build a compact version of the detail panel for the side panel
    return `
        <div class="apartment-analysis-compact">
            <!-- Overall Score -->
            <div style="background: linear-gradient(135deg, #0066cc 0%, #004999 100%); padding: 16px; border-radius: 10px; margin-bottom: 16px; color: white; text-align: center;">
                <div style="font-size: 12px; text-transform: uppercase; opacity: 0.9; margin-bottom: 4px;">Overall Score</div>
                <div style="font-size: 36px; font-weight: 700;">${apartment.score || 'N/A'}</div>
                ${apartment.score_min && apartment.score_max ? `
                    <div style="font-size: 12px; opacity: 0.8;">Range: ${apartment.score_min} - ${apartment.score_max}</div>
                ` : ''}
            </div>
            
            <!-- Component Scores Grid -->
            <div style="margin-bottom: 16px;">
                <h5 style="margin: 0 0 10px 0; font-size: 13px; color: #666; text-transform: uppercase;">Component Scores</h5>
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px; font-size: 13px;">
                    ${apartment.commute_score !== undefined && apartment.commute_score !== null ? `
                        <div style="display: flex; justify-content: space-between; padding: 8px 10px; background: #f8f9fa; border-radius: 6px;">
                            <span>🚗 Commute</span>
                            <strong>${parseFloat(apartment.commute_score).toFixed(1)}</strong>
                        </div>
                    ` : ''}
                    ${apartment.safety_score !== undefined && apartment.safety_score !== null ? `
                        <div style="display: flex; justify-content: space-between; padding: 8px 10px; background: #f8f9fa; border-radius: 6px;">
                            <span>🛡️ Safety</span>
                            <strong>${parseFloat(apartment.safety_score).toFixed(1)}</strong>
                        </div>
                    ` : ''}
                    ${apartment.wfh_score !== undefined && apartment.wfh_score !== null ? `
                        <div style="display: flex; justify-content: space-between; padding: 8px 10px; background: #f8f9fa; border-radius: 6px;">
                            <span>💻 WFH</span>
                            <strong>${parseFloat(apartment.wfh_score).toFixed(1)}</strong>
                        </div>
                    ` : ''}
                    ${apartment.happening_score !== undefined && apartment.happening_score !== null ? `
                        <div style="display: flex; justify-content: space-between; padding: 8px 10px; background: #f8f9fa; border-radius: 6px;">
                            <span>🎉 Happening</span>
                            <strong>${parseFloat(apartment.happening_score).toFixed(1)}</strong>
                        </div>
                    ` : ''}
                    ${apartment.parking_score !== undefined && apartment.parking_score !== null ? `
                        <div style="display: flex; justify-content: space-between; padding: 8px 10px; background: #f8f9fa; border-radius: 6px;">
                            <span>🅿️ Parking</span>
                            <strong>${parseFloat(apartment.parking_score).toFixed(1)}</strong>
                        </div>
                    ` : ''}
                    ${apartment.gym_score !== undefined && apartment.gym_score !== null ? `
                        <div style="display: flex; justify-content: space-between; padding: 8px 10px; background: #f8f9fa; border-radius: 6px;">
                            <span>🏋️ Gym</span>
                            <strong>${parseFloat(apartment.gym_score).toFixed(1)}</strong>
                        </div>
                    ` : ''}
                    ${apartment.laundry_score !== undefined && apartment.laundry_score !== null ? `
                        <div style="display: flex; justify-content: space-between; padding: 8px 10px; background: #f8f9fa; border-radius: 6px;">
                            <span>🧺 Laundry</span>
                            <strong>${parseFloat(apartment.laundry_score).toFixed(1)}</strong>
                        </div>
                    ` : ''}
                    ${apartment.space_luxury_score !== undefined && apartment.space_luxury_score !== null ? `
                        <div style="display: flex; justify-content: space-between; padding: 8px 10px; background: #f8f9fa; border-radius: 6px;">
                            <span>📐 Space</span>
                            <strong>${parseFloat(apartment.space_luxury_score).toFixed(1)}</strong>
                        </div>
                    ` : ''}
                </div>
            </div>
            
            <!-- Key Details -->
            <div style="background: #f8f9fa; border-radius: 10px; padding: 12px;">
                <h5 style="margin: 0 0 10px 0; font-size: 13px; color: #666; text-transform: uppercase;">Key Details</h5>
                <div style="display: grid; gap: 6px; font-size: 13px;">
                    ${apartment.price !== undefined ? `
                        <div style="display: flex; justify-content: space-between;">
                            <span style="color: #666;">💰 Monthly Cost</span>
                            <strong>$${apartment.price.toLocaleString()}</strong>
                        </div>
                        ${apartment.parking_cost > 0 ? `
                            <div style="display: flex; justify-content: space-between; padding-left: 20px; font-size: 12px; color: #888;">
                                <span>Rent: $${apartment.base_price?.toLocaleString() || apartment.price}</span>
                                <span>Parking: $${apartment.parking_cost}</span>
                            </div>
                        ` : ''}
                    ` : ''}
                    <div style="display: flex; justify-content: space-between;">
                        <span style="color: #666;">🛏️ Bedrooms</span>
                        <strong>${apartment.bedrooms || 'N/A'}</strong>
                    </div>
                    <div style="display: flex; justify-content: space-between;">
                        <span style="color: #666;">🚿 Bathrooms</span>
                        <strong>${apartment.bathrooms || 'N/A'}</strong>
                    </div>
                    <div style="display: flex; justify-content: space-between;">
                        <span style="color: #666;">📐 Size</span>
                        <strong>${apartment.sqft ? apartment.sqft + ' sqft' : 'N/A'}</strong>
                    </div>
                    <div style="display: flex; justify-content: space-between;">
                        <span style="color: #666;">🚗 Your Commute</span>
                        <strong>${apartment.commute_you ? apartment.commute_you + ' min' : 'N/A'}</strong>
                    </div>
                    <div style="display: flex; justify-content: space-between;">
                        <span style="color: #666;">🚇 Partner Commute</span>
                        <strong>${apartment.commute_partner ? apartment.commute_partner + ' min' : 'N/A'}</strong>
                    </div>
                </div>
            </div>
            
            <!-- Action Button -->
            <div style="margin-top: 16px;">
                <button class="btn btn-primary" style="width: 100%; padding: 10px; font-size: 14px;" onclick="window.open('/','_blank').focus(); setTimeout(() => {
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



