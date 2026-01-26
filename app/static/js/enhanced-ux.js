/**
 * ENHANCED MOBILE UX & INTERACTIONS
 * Beautiful, smooth, human-centered interactions
 */

(function() {
    'use strict';
    
    // =====================================================
    // 🎨 SMOOTH SCROLL WITH OFFSET
    // =====================================================
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function (e) {
            const href = this.getAttribute('href');
            if (href === '#') return;
            
            e.preventDefault();
            const target = document.querySelector(href);
            if (!target) return;
            
            const headerHeight = document.querySelector('.site-header')?.offsetHeight || 0;
            const targetPosition = target.getBoundingClientRect().top + window.pageYOffset;
            const offsetPosition = targetPosition - headerHeight - 20;
            
            window.scrollTo({
                top: offsetPosition,
                behavior: 'smooth'
            });
        });
    });
    
    // =====================================================
    // 📱 ENHANCED MOBILE NAVIGATION
    // =====================================================
    const navToggle = document.querySelector('.nav-toggle');
    const nav = document.querySelector('.nav');
    const navOverlay = document.querySelector('.nav-overlay');
    const body = document.body;
    
    function openNav() {
        if (!nav) return;
        nav.classList.add('is-open');
        if (navOverlay) navOverlay.classList.add('is-visible');
        if (navToggle) navToggle.setAttribute('aria-expanded', 'true');
        body.style.overflow = 'hidden';
        
        // Add stagger animation to nav items
        const navLinks = nav.querySelectorAll('.nav-link');
        navLinks.forEach((link, index) => {
            link.style.animation = `fadeInUp 0.4s ease forwards ${index * 0.05}s`;
        });
    }
    
    function closeNav() {
        if (!nav) return;
        nav.classList.remove('is-open');
        if (navOverlay) navOverlay.classList.remove('is-visible');
        if (navToggle) navToggle.setAttribute('aria-expanded', 'false');
        body.style.overflow = '';
    }
    
    if (navToggle) {
        navToggle.addEventListener('click', function(e) {
            // Defensive: never throw on pages without the nav element.
            if (!nav) return;

            // Keep the click focused on the toggle.
            if (e && typeof e.preventDefault === 'function') e.preventDefault();

            const isOpen = nav.classList.contains('is-open');
            if (isOpen) {
                closeNav();
            } else {
                openNav();
            }
        });
    }
    
    if (navOverlay) {
        navOverlay.addEventListener('click', closeNav);
    }
    
    // Close nav when clicking a link
    if (nav) {
        nav.querySelectorAll('a').forEach(link => {
            link.addEventListener('click', function() {
                if (window.innerWidth < 960) {
                    closeNav();
                }
            });
        });
    }
    
    // Close on escape key
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape' && nav && nav.classList.contains('is-open')) {
            closeNav();
        }
    });
    
    // =====================================================
    // 🔽 TOOLS DROPDOWN NAVIGATION
    // =====================================================
    const toolsSpinner = document.querySelector('[data-tools-spinner]');
    if (toolsSpinner instanceof HTMLSelectElement) {
        toolsSpinner.addEventListener('change', function() {
            const target = toolsSpinner.value;
            if (target) {
                window.location.href = target;
            }
        });
    }
    
    // =====================================================
    // 🎭 INTERSECTION OBSERVER - REVEAL ON SCROLL
    // =====================================================
    const observerOptions = {
        root: null,
        rootMargin: '0px',
        threshold: 0.1
    };
    
    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.style.opacity = '1';
                entry.target.style.transform = 'translateY(0)';
                observer.unobserve(entry.target);
            }
        });
    }, observerOptions);
    
    // Observe all reveal elements
    document.querySelectorAll('.reveal').forEach(el => {
        el.style.opacity = '0';
        el.style.transform = 'translateY(30px)';
        el.style.transition = 'all 0.8s cubic-bezier(0.4, 0, 0.2, 1)';
        observer.observe(el);
    });
    
    // =====================================================
    // ⚡ LAZY LOAD IMAGES WITH FADE-IN
    // =====================================================
    const imageObserver = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                const img = entry.target;
                
                if (img.dataset.src) {
                    img.src = img.dataset.src;
                    img.removeAttribute('data-src');
                }
                
                if (img.dataset.srcset) {
                    img.srcset = img.dataset.srcset;
                    img.removeAttribute('data-srcset');
                }
                
                img.addEventListener('load', function() {
                    img.classList.add('is-loaded');
                    img.classList.remove('is-loading');
                });
                
                imageObserver.unobserve(img);
            }
        });
    }, {
        rootMargin: '50px'
    });
    
    document.querySelectorAll('img[data-src], img[loading="lazy"]').forEach(img => {
        img.classList.add('is-loading');
        imageObserver.observe(img);
    });
    
    // =====================================================
    // 🎨 ENHANCED TOAST NOTIFICATIONS
    // =====================================================
    function dismissToast(toast) {
        toast.style.animation = 'slideInRight 0.3s ease reverse';
        setTimeout(() => {
            toast.remove();
        }, 300);
    }
    
    document.querySelectorAll('.toast__close').forEach(btn => {
        btn.addEventListener('click', function() {
            const toast = this.closest('.toast');
            if (toast) dismissToast(toast);
        });
    });
    
    // Auto-dismiss toasts
    document.querySelectorAll('.toast[data-timeout]').forEach(toast => {
        const timeout = parseInt(toast.dataset.timeout) || 4000;
        setTimeout(() => {
            dismissToast(toast);
        }, timeout);
    });
    
    // =====================================================
    // 💫 RIPPLE EFFECT FOR BUTTONS
    // =====================================================
    document.querySelectorAll('.btn, .ripple').forEach(el => {
        el.addEventListener('click', function(e) {
            const ripple = document.createElement('span');
            ripple.classList.add('ripple-effect');
            
            const rect = this.getBoundingClientRect();
            const size = Math.max(rect.width, rect.height);
            const x = e.clientX - rect.left - size / 2;
            const y = e.clientY - rect.top - size / 2;
            
            ripple.style.cssText = `
                position: absolute;
                border-radius: 50%;
                background: rgba(255, 255, 255, 0.6);
                width: ${size}px;
                height: ${size}px;
                left: ${x}px;
                top: ${y}px;
                pointer-events: none;
                animation: rippleAnimation 0.6s ease-out;
            `;
            
            this.style.position = 'relative';
            this.style.overflow = 'hidden';
            this.appendChild(ripple);
            
            setTimeout(() => ripple.remove(), 600);
        });
    });
    
    // Ripple animation keyframes
    if (!document.querySelector('#rippleAnimation')) {
        const style = document.createElement('style');
        style.id = 'rippleAnimation';
        style.textContent = `
            @keyframes rippleAnimation {
                from {
                    transform: scale(0);
                    opacity: 1;
                }
                to {
                    transform: scale(4);
                    opacity: 0;
                }
            }
        `;
        document.head.appendChild(style);
    }
    
    // =====================================================
    // 🎯 STICKY HEADER ON SCROLL
    // =====================================================
    let lastScroll = 0;
    const header = document.querySelector('.site-header');
    
    if (header) {
        window.addEventListener('scroll', function() {
            const currentScroll = window.pageYOffset;
            
            if (currentScroll <= 0) {
                header.style.boxShadow = 'none';
                header.style.transform = 'translateY(0)';
            } else if (currentScroll > lastScroll && currentScroll > 100) {
                // Scrolling down
                header.style.transform = 'translateY(-100%)';
            } else {
                // Scrolling up
                header.style.transform = 'translateY(0)';
                header.style.boxShadow = '0 4px 20px rgba(0, 0, 0, 0.06)';
            }
            
            lastScroll = currentScroll;
        }, { passive: true });
    }
    
    // =====================================================
    // 📏 DYNAMIC VIEWPORT HEIGHT (Mobile Safari Fix)
    // =====================================================
    function setVH() {
        const vh = window.innerHeight * 0.01;
        document.documentElement.style.setProperty('--vh', `${vh}px`);
    }
    
    setVH();
    window.addEventListener('resize', setVH);
    window.addEventListener('orientationchange', setVH);
    
    // =====================================================
    // 🎨 SCROLL PROGRESS INDICATOR
    // =====================================================
    const progressBar = document.createElement('div');
    progressBar.style.cssText = `
        position: fixed;
        top: 0;
        left: 0;
        width: 0;
        height: 3px;
        background: linear-gradient(90deg, #5B8DEE 0%, #FF8C42 100%);
        z-index: 9999;
        transition: width 0.1s ease;
    `;
    document.body.appendChild(progressBar);
    
    window.addEventListener('scroll', function() {
        const winScroll = document.body.scrollTop || document.documentElement.scrollTop;
        const height = document.documentElement.scrollHeight - document.documentElement.clientHeight;
        const scrolled = (winScroll / height) * 100;
        progressBar.style.width = scrolled + '%';
    }, { passive: true });
    
    // =====================================================
    // 💬 ENHANCED FORM VALIDATION
    // =====================================================
    document.querySelectorAll('input[required], textarea[required], select[required]').forEach(field => {
        field.addEventListener('blur', function() {
            if (!this.value.trim()) {
                this.style.borderColor = '#ef4444';
                this.setAttribute('aria-invalid', 'true');
            } else {
                this.style.borderColor = '';
                this.removeAttribute('aria-invalid');
            }
        });
        
        field.addEventListener('input', function() {
            if (this.value.trim()) {
                this.style.borderColor = '';
                this.removeAttribute('aria-invalid');
            }
        });
    });
    
    // =====================================================
    // 🔍 SEARCH INPUT ENHANCEMENT
    // =====================================================
    document.querySelectorAll('input[type="search"]').forEach(input => {
        const clearBtn = document.createElement('button');
        clearBtn.type = 'button';
        clearBtn.innerHTML = '×';
        clearBtn.style.cssText = `
            position: absolute;
            right: 12px;
            top: 50%;
            transform: translateY(-50%);
            background: none;
            border: none;
            font-size: 1.5rem;
            color: rgba(0, 0, 0, 0.4);
            cursor: pointer;
            display: none;
            padding: 0;
            width: 24px;
            height: 24px;
            align-items: center;
            justify-content: center;
        `;
        
        const wrapper = input.parentElement;
        if (wrapper) {
            wrapper.style.position = 'relative';
            wrapper.appendChild(clearBtn);
        }
        
        input.addEventListener('input', function() {
            clearBtn.style.display = this.value ? 'flex' : 'none';
        });
        
        clearBtn.addEventListener('click', function() {
            input.value = '';
            input.focus();
            clearBtn.style.display = 'none';
            input.dispatchEvent(new Event('input', { bubbles: true }));
        });
    });
    
    // =====================================================
    // 🎭 CARD HOVER 3D TILT EFFECT (Desktop Only)
    // =====================================================
    if (window.innerWidth > 1024) {
        document.querySelectorAll('.plan-card, .card').forEach(card => {
            card.addEventListener('mousemove', function(e) {
                const rect = this.getBoundingClientRect();
                const x = e.clientX - rect.left;
                const y = e.clientY - rect.top;
                
                const centerX = rect.width / 2;
                const centerY = rect.height / 2;
                
                const rotateX = ((y - centerY) / centerY) * -10;
                const rotateY = ((x - centerX) / centerX) * 10;
                
                this.style.transform = `perspective(1000px) rotateX(${rotateX}deg) rotateY(${rotateY}deg) translateZ(10px)`;
            });
            
            card.addEventListener('mouseleave', function() {
                this.style.transform = '';
            });
        });
    }
    
    // =====================================================
    // 📱 SWIPE GESTURES FOR MOBILE
    // =====================================================
    let touchStartX = 0;
    let touchEndX = 0;
    
    function handleSwipe() {
        const swipeThreshold = 100;
        const diff = touchEndX - touchStartX;
        
        if (Math.abs(diff) > swipeThreshold) {
            if (diff > 0) {
                // Swipe right
                if (nav && !nav.classList.contains('is-open')) {
                    // Could open drawer or navigate
                }
            } else {
                // Swipe left
                if (nav && nav.classList.contains('is-open')) {
                    closeNav();
                }
            }
        }
    }
    
    document.addEventListener('touchstart', function(e) {
        touchStartX = e.changedTouches[0].screenX;
    }, { passive: true });
    
    document.addEventListener('touchend', function(e) {
        touchEndX = e.changedTouches[0].screenX;
        handleSwipe();
    }, { passive: true });
    
    // =====================================================
    // 🎨 BACK TO TOP BUTTON
    // =====================================================
    const backToTop = document.createElement('button');
    backToTop.className = 'fab';
    backToTop.innerHTML = '<i class="fa-solid fa-arrow-up"></i>';
    backToTop.setAttribute('aria-label', 'Back to top');
    backToTop.style.opacity = '0';
    backToTop.style.visibility = 'hidden';
    backToTop.style.transition = 'all 0.3s ease';
    
    document.body.appendChild(backToTop);
    
    window.addEventListener('scroll', function() {
        if (window.pageYOffset > 300) {
            backToTop.style.opacity = '1';
            backToTop.style.visibility = 'visible';
        } else {
            backToTop.style.opacity = '0';
            backToTop.style.visibility = 'hidden';
        }
    }, { passive: true });
    
    backToTop.addEventListener('click', function() {
        window.scrollTo({
            top: 0,
            behavior: 'smooth'
        });
    });
    
    // =====================================================
    // 📐 RESPONSIVE IMAGES - ASPECT RATIO FIX
    // =====================================================
    function fixImageAspectRatios() {
        document.querySelectorAll('img').forEach(img => {
            if (!img.complete) {
                img.addEventListener('load', function() {
                    const parent = this.parentElement;
                    if (parent && parent.classList.contains('aspect-16-9')) {
                        this.style.aspectRatio = '16 / 9';
                        this.style.objectFit = 'cover';
                    }
                });
            }
        });
    }
    
    fixImageAspectRatios();
    
    // =====================================================
    // 🎯 FOCUS TRAP FOR MODALS
    // =====================================================
    function trapFocus(element) {
        const focusableElements = element.querySelectorAll(
            'a[href], button:not([disabled]), textarea, input, select'
        );
        const firstFocusable = focusableElements[0];
        const lastFocusable = focusableElements[focusableElements.length - 1];
        
        element.addEventListener('keydown', function(e) {
            if (e.key !== 'Tab') return;
            
            if (e.shiftKey) {
                if (document.activeElement === firstFocusable) {
                    lastFocusable.focus();
                    e.preventDefault();
                }
            } else {
                if (document.activeElement === lastFocusable) {
                    firstFocusable.focus();
                    e.preventDefault();
                }
            }
        });
    }
    
    // Apply to mobile nav
    if (nav) {
        trapFocus(nav);
    }
    
    // =====================================================
    // 🎨 CONSOLE MESSAGE
    // =====================================================
    console.log(
        '%c✨ Enhanced Mobile UX Active! ✨',
        'color: #5B8DEE; font-size: 20px; font-weight: bold; text-shadow: 2px 2px 4px rgba(0,0,0,0.2);'
    );
    console.log(
        '%cEnjoy the smooth, beautiful, human-centered experience! 🎉',
        'color: #FF8C42; font-size: 14px;'
    );
    
})();
