

// Global variables
let sidebarOpen = false;
let currentToast = null;

// Initialize app when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
   initializeApp();
});

function initializeApp() {
   setupGlobalEventListeners();
   setupSidebar();
   initializeDarkMode(); // New function
   initializeTooltips();
   
   // Page-specific initializations
   const currentPage = getCurrentPage();
   switch(currentPage) {
       case 'dashboard':
           initializeDashboard();
           break;
       case 'attendance':
           initializeAttendance();
           break;
       case 'students':
           initializeStudents();
           break;
       case 'reports':
           initializeReports();
           break;
   }
}

/**
* Initialize Dark Mode Logic
*/
function initializeDarkMode() {
   const themeToggle = document.getElementById('themeToggle');
   const icon = themeToggle.querySelector('i');
   
   // Check saved preference
   const currentTheme = localStorage.getItem('theme');
   if (currentTheme === 'dark') {
       document.documentElement.setAttribute('data-theme', 'dark');
       icon.classList.remove('fa-moon');
       icon.classList.add('fa-sun');
   }

   // Toggle event
   if (themeToggle) {
       themeToggle.addEventListener('click', () => {
           const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
           
           if (isDark) {
               document.documentElement.removeAttribute('data-theme');
               localStorage.setItem('theme', 'light');
               icon.classList.remove('fa-sun');
               icon.classList.add('fa-moon');
           } else {
               document.documentElement.setAttribute('data-theme', 'dark');
               localStorage.setItem('theme', 'dark');
               icon.classList.remove('fa-moon');
               icon.classList.add('fa-sun');
           }
       });
   }
}


/**
 * Initialize the application
 */
function initializeApp() {
    setupGlobalEventListeners();
    setupSidebar();
    initializeTooltips();
    
    // Page-specific initializations
    const currentPage = getCurrentPage();
    switch(currentPage) {
        case 'dashboard':
            initializeDashboard();
            break;
        case 'attendance':
            initializeAttendance();
            break;
        case 'students':
            initializeStudents();
            break;
        case 'reports':
            initializeReports();
            break;
    }
}

/**
 * Get current page based on URL
 */
function getCurrentPage() {
    const path = window.location.pathname;
    if (path === '/' || path === '/dashboard') return 'dashboard';
    if (path === '/attendance') return 'attendance';
    if (path === '/students') return 'students';
    if (path === '/reports') return 'reports';
    return 'dashboard';
}

/**
 * Setup global event listeners
 */
function setupGlobalEventListeners() {
    // Click outside modal to close
    document.addEventListener('click', function(e) {
        if (e.target.classList.contains('modal')) {
            closeAllModals();
        }
    });
    
    // Escape key to close modals
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape') {
            closeAllModals();
        }
    });
    
    // Handle form submissions
    document.addEventListener('submit', function(e) {
        const form = e.target;
        if (form.classList.contains('ajax-form')) {
            e.preventDefault();
            handleAjaxForm(form);
        }
    });
}

/**
 * Setup sidebar functionality
 */
function setupSidebar() {
    const menuToggle = document.getElementById('menuToggle');
    const sidebar = document.querySelector('.sidebar');
    
    if (menuToggle && sidebar) {
        menuToggle.addEventListener('click', function() {
            toggleSidebar();
        });
        
        // Close sidebar when clicking outside on mobile
        document.addEventListener('click', function(e) {
            if (window.innerWidth <= 1024 && 
                sidebarOpen && 
                !sidebar.contains(e.target) && 
                !menuToggle.contains(e.target)) {
                closeSidebar();
            }
        });
    }
    
    // Handle window resize
    window.addEventListener('resize', function() {
        if (window.innerWidth > 1024) {
            closeSidebar();
        }
    });
}

/**
 * Toggle sidebar visibility
 */
function toggleSidebar() {
    const sidebar = document.querySelector('.sidebar');
    if (sidebar) {
        sidebarOpen = !sidebarOpen;
        sidebar.classList.toggle('open', sidebarOpen);
    }
}

/**
 * Close sidebar
 */
function closeSidebar() {
    const sidebar = document.querySelector('.sidebar');
    if (sidebar) {
        sidebarOpen = false;
        sidebar.classList.remove('open');
    }
}

/**
 * Initialize tooltips (placeholder for future implementation)
 */
function initializeTooltips() {
    // Placeholder for tooltip initialization
    // Could use a library like Tippy.js in the future
}

/**
 * Dashboard specific initialization
 */
function initializeDashboard() {
    // Animate stats cards
    const statCards = document.querySelectorAll('.stat-card');
    statCards.forEach((card, index) => {
        setTimeout(() => {
            card.style.opacity = '1';
            card.style.transform = 'translateY(0)';
        }, index * 150);
    });
    
    // Add hover effects to quick actions
    const actionCards = document.querySelectorAll('.action-card');
    actionCards.forEach(card => {
        card.addEventListener('mouseenter', function() {
            this.style.transform = 'translateY(-4px)';
        });
        
        card.addEventListener('mouseleave', function() {
            this.style.transform = 'translateY(-2px)';
        });
    });
}

/**
 * Attendance page specific initialization
 */
function initializeAttendance() {
    // This is handled in the attendance.html template
    // Additional global functionality can be added here
}

/**
 * Students page specific initialization
 */
function initializeStudents() {
    // This is handled in the students.html template
    // Additional global functionality can be added here
}

/**
 * Reports page specific initialization
 */
function initializeReports() {
    // This is handled in the reports.html template
    // Additional global functionality can be added here
}

/**
 * Show toast notification
 */
function showToast(message, type = 'info', duration = 4000) {
    // Clear existing toast
    if (currentToast) {
        clearTimeout(currentToast.timeout);
        currentToast.element.remove();
    }
    
    // Create toast element
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.innerHTML = `
        <div class="toast-content">
            <i class="toast-icon"></i>
            <span class="toast-message">${message}</span>
        </div>
    `;
    
    // Add to document
    document.body.appendChild(toast);
    
    // Show toast
    setTimeout(() => {
        toast.classList.add('show');
    }, 100);
    
    // Hide toast after duration
    const timeout = setTimeout(() => {
        hideToast(toast);
    }, duration);
    
    // Store current toast reference
    currentToast = {
        element: toast,
        timeout: timeout
    };
    
    // Allow manual close
    toast.addEventListener('click', () => {
        hideToast(toast);
    });
}

/**
 * Hide toast notification
 */
function hideToast(toast) {
    toast.classList.remove('show');
    setTimeout(() => {
        if (toast.parentNode) {
            toast.parentNode.removeChild(toast);
        }
    }, 300);
    
    if (currentToast && currentToast.element === toast) {
        clearTimeout(currentToast.timeout);
        currentToast = null;
    }
}

/**
 * Close all modals
 */
function closeAllModals() {
    const modals = document.querySelectorAll('.modal');
    modals.forEach(modal => {
        modal.style.display = 'none';
    });
}

/**
 * Handle AJAX form submissions
 */
async function handleAjaxForm(form) {
    const formData = new FormData(form);
    const submitBtn = form.querySelector('button[type="submit"]');
    const originalText = submitBtn.innerHTML;
    
    // Show loading state
    submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Saving...';
    submitBtn.disabled = true;
    
    try {
        const response = await fetch(form.action || window.location.pathname, {
            method: form.method || 'POST',
            body: formData
        });
        
        const result = await response.json();
        
        if (result.success) {
            showToast(result.message || 'Operation completed successfully!', 'success');
            
            // Reset form if specified
            if (form.dataset.resetOnSuccess === 'true') {
                form.reset();
            }
            
            // Close modal if form is inside one
            const modal = form.closest('.modal');
            if (modal) {
                modal.style.display = 'none';
            }
            
            // Refresh page if specified
            if (form.dataset.refreshOnSuccess === 'true') {
                setTimeout(() => {
                    window.location.reload();
                }, 1000);
            }
            
        } else {
            showToast(result.message || 'An error occurred. Please try again.', 'error');
        }
        
    } catch (error) {
        console.error('Form submission error:', error);
        showToast('Network error. Please check your connection and try again.', 'error');
        
    } finally {
        // Restore button state
        submitBtn.innerHTML = originalText;
        submitBtn.disabled = false;
    }
}

/**
 * Utility function to format dates
 */
function formatDate(date, format = 'short') {
    const options = {
        short: { 
            year: 'numeric', 
            month: 'short', 
            day: 'numeric' 
        },
        long: { 
            weekday: 'long', 
            year: 'numeric', 
            month: 'long', 
            day: 'numeric' 
        },
        time: {
            hour: '2-digit',
            minute: '2-digit',
            hour12: true
        }
    };
    
    return new Intl.DateTimeFormat('en-US', options[format]).format(date);
}

/**
 * Utility function to debounce function calls
 */
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

/**
 * Utility function to validate email
 */
function validateEmail(email) {
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return emailRegex.test(email);
}

/**
 * Utility function to validate required fields
 */
function validateForm(form) {
    const requiredFields = form.querySelectorAll('[required]');
    let isValid = true;
    let firstInvalidField = null;
    
    requiredFields.forEach(field => {
        const value = field.value.trim();
        
        // Remove previous error styles
        field.classList.remove('error');
        
        // Check if field is empty
        if (!value) {
            field.classList.add('error');
            isValid = false;
            if (!firstInvalidField) firstInvalidField = field;
        }
        
        // Additional validation for email fields
        if (field.type === 'email' && value && !validateEmail(value)) {
            field.classList.add('error');
            isValid = false;
            if (!firstInvalidField) firstInvalidField = field;
        }
    });
    
    // Focus on first invalid field
    if (!isValid && firstInvalidField) {
        firstInvalidField.focus();
    }
    
    return isValid;
}

/**
 * Utility function to animate elements
 */
function animateElement(element, animation, duration = 300) {
    return new Promise(resolve => {
        element.style.animation = `${animation} ${duration}ms ease-in-out`;
        
        setTimeout(() => {
            element.style.animation = '';
            resolve();
        }, duration);
    });
}

/**
 * Utility function to scroll to element
 */
function scrollToElement(element, offset = 0) {
    const elementPosition = element.offsetTop - offset;
    
    window.scrollTo({
        top: elementPosition,
        behavior: 'smooth'
    });
}

/**
 * Local storage utilities
 */
const storage = {
    set: (key, value) => {
        try {
            localStorage.setItem(key, JSON.stringify(value));
        } catch (e) {
            console.warn('LocalStorage not available:', e);
        }
    },
    
    get: (key, defaultValue = null) => {
        try {
            const item = localStorage.getItem(key);
            return item ? JSON.parse(item) : defaultValue;
        } catch (e) {
            console.warn('LocalStorage not available:', e);
            return defaultValue;
        }
    },
    
    remove: (key) => {
        try {
            localStorage.removeItem(key);
        } catch (e) {
            console.warn('LocalStorage not available:', e);
        }
    }
};

/**
 * API utility functions
 */
const api = {
    get: async (url) => {
        try {
            const response = await fetch(url, {
                method: 'GET',
                headers: {
                    'Content-Type': 'application/json',
                }
            });
            return await response.json();
        } catch (error) {
            console.error('API GET error:', error);
            throw error;
        }
    },
    
    post: async (url, data) => {
        try {
            const response = await fetch(url, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(data)
            });
            return await response.json();
        } catch (error) {
            console.error('API POST error:', error);
            throw error;
        }
    },
    
    put: async (url, data) => {
        try {
            const response = await fetch(url, {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(data)
            });
            return await response.json();
        } catch (error) {
            console.error('API PUT error:', error);
            throw error;
        }
    },
    
    delete: async (url) => {
        try {
            const response = await fetch(url, {
                method: 'DELETE',
                headers: {
                    'Content-Type': 'application/json',
                }
            });
            return await response.json();
        } catch (error) {
            console.error('API DELETE error:', error);
            throw error;
        }
    }
};

// Export for use in other files (if using modules)
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        showToast,
        closeAllModals,
        validateForm,
        validateEmail,
        formatDate,
        debounce,
        animateElement,
        scrollToElement,
        storage,
        api
    };
}

