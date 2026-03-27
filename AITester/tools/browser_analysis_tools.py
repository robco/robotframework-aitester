# Apache License 2.0
# Copyright (c) 2026 Róbert Malovec

"""
Browser analysis tools — Specialized tools for understanding page state.

These tools help the AI agent understand the current state of a web page
by parsing the DOM and extracting structured information about interactive
elements, page structure, and visible content.
"""

import json
import logging
from typing import Any, Dict
from strands import tool
from robot.libraries.BuiltIn import BuiltIn, RobotNotRunningError

from .common_tools import instrument_tool_list

logger = logging.getLogger(__name__)
_PAGE_SNAPSHOT_CACHE: Dict[str, Dict[str, Any]] = {}


def _get_selenium():
    """Get the SeleniumLibrary instance from Robot Framework."""
    bi = BuiltIn()
    lib_name = "SeleniumLibrary"
    try:
        override = bi.get_variable_value("${AITESTER_SELENIUM_LIBRARY}")
        if override:
            lib_name = override
    except RobotNotRunningError:
        pass
    try:
        return bi.get_library_instance(lib_name)
    except Exception as exc:
        raise RuntimeError(
            f"SeleniumLibrary instance '{lib_name}' not found. "
            "Ensure SeleniumLibrary is imported or set selenium_library "
            "when importing AITester."
        ) from exc


def _get_snapshot_cache_key(driver) -> str:
    return str(getattr(driver, "session_id", None) or id(driver))


def invalidate_page_snapshot_cache(driver=None) -> None:
    if driver is None:
        _PAGE_SNAPSHOT_CACHE.clear()
        return
    _PAGE_SNAPSHOT_CACHE.pop(_get_snapshot_cache_key(driver), None)


def _build_page_snapshot(driver) -> Dict[str, Any]:
    js_code = """
    function safeText(value, limit) {
        return (value || '').trim().substring(0, limit);
    }

    function cssAttributeSelector(attributeName, value) {
        if (!value) return null;
        return 'css=[' + attributeName + '=' + JSON.stringify(String(value)) + ']';
    }

    function getDomXPath(element) {
        if (!element || element.nodeType !== Node.ELEMENT_NODE) return null;
        const segments = [];
        let current = element;
        while (current && current.nodeType === Node.ELEMENT_NODE) {
            const tag = current.tagName.toLowerCase();
            if (tag === 'html') {
                segments.unshift('html[1]');
                break;
            }
            let index = 1;
            let sibling = current.previousElementSibling;
            while (sibling) {
                if (
                    sibling.tagName &&
                    sibling.tagName.toLowerCase() === tag
                ) {
                    index += 1;
                }
                sibling = sibling.previousElementSibling;
            }
            segments.unshift(tag + '[' + index + ']');
            current = current.parentElement;
        }
        if (!segments.length) return null;
        return '//' + segments.join('/');
    }

    function getLocator(element) {
        if (!element) return null;
        if (element.id) return 'id=' + element.id;
        const testId = element.getAttribute('data-testid');
        if (testId) return cssAttributeSelector('data-testid', testId);
        if (element.name) return cssAttributeSelector('name', element.name);
        const aria = element.getAttribute('aria-label');
        if (aria) return cssAttributeSelector('aria-label', aria);
        const domXPath = getDomXPath(element);
        return domXPath ? 'xpath=' + domXPath : null;
    }

    function isVisible(element) {
        const rect = element.getBoundingClientRect();
        const ownerWindow = (
            element &&
            element.ownerDocument &&
            element.ownerDocument.defaultView
        ) ? element.ownerDocument.defaultView : window;
        const style = ownerWindow.getComputedStyle(element);
        return rect.width > 0 && rect.height > 0 &&
            style.display !== 'none' &&
            style.visibility !== 'hidden';
    }

    function normalizeSpace(value) {
        return String(value || '').replace(/\\s+/g, ' ').trim();
    }

    function getElementText(element, limit) {
        if (!element) return '';
        return safeText(
            normalizeSpace(
                element.innerText || element.textContent ||
                element.getAttribute('aria-label') || element.value || ''
            ),
            limit
        );
    }

    function getControlledPopupRoots(element) {
        const roots = [];

        function push(candidate) {
            if (!candidate || roots.includes(candidate)) return;
            roots.push(candidate);
        }

        function pushIds(rawValue) {
            normalizeSpace(rawValue).split(' ').filter(Boolean).forEach(id => {
                push(document.getElementById(id));
            });
        }

        if (!element) return roots;

        pushIds(element.getAttribute('aria-controls'));
        pushIds(element.getAttribute('aria-owns'));

        const owner = element.closest('[role="combobox"], [role="listbox"]');
        if (owner) {
            push(owner);
            pushIds(owner.getAttribute('aria-controls'));
            pushIds(owner.getAttribute('aria-owns'));
        }

        document.querySelectorAll(
            '[role="listbox"], [role="menu"], [role="tree"], [role="grid"], ' +
            '[data-state="open"], [data-open="true"], [data-headlessui-state]'
        ).forEach(candidate => {
            if (isVisible(candidate)) push(candidate);
        });

        return roots;
    }

    function collectOptionLikeEntries(element, limit) {
        const options = [];
        const seen = new Set();

        function pushOption(candidate) {
            if (!candidate || options.length >= limit) return;
            const text = getElementText(candidate, 80);
            const value = safeText(
                normalizeSpace(
                    candidate.value ||
                    candidate.getAttribute('value') ||
                    candidate.getAttribute('data-value') ||
                    candidate.getAttribute('data-key') ||
                    ''
                ),
                80
            ) || null;
            const key = (text || '') + '|' + (value || '');
            if ((!text && !value) || seen.has(key)) return;
            seen.add(key);
            options.push({
                text: text || null,
                value: value,
                selected: candidate.selected || candidate.getAttribute('aria-selected') === 'true',
                disabled: candidate.disabled || candidate.getAttribute('aria-disabled') === 'true',
            });
        }

        if (!element) return options;

        if (element.tagName && element.tagName.toLowerCase() === 'select') {
            Array.from(element.options || []).forEach(option => pushOption(option));
            return options;
        }

        const optionSelectors = [
            '[role="option"]',
            '[role="menuitem"]',
            '[role="menuitemradio"]',
            '[role="menuitemcheckbox"]',
            '[data-value]',
            'li',
            'button',
        ];

        getControlledPopupRoots(element).forEach(root => {
            root.querySelectorAll(optionSelectors.join(', ')).forEach(candidate => {
                if (!isVisible(candidate) || candidate === element) return;
                pushOption(candidate);
            });
        });

        return options;
    }

    function describeControl(element) {
        const tag = element.tagName.toLowerCase();
        const role = (element.getAttribute('role') || '').toLowerCase();
        const type = (element.type || '').toLowerCase();
        const hasPopup = (element.getAttribute('aria-haspopup') || '').toLowerCase();
        const autocomplete = (element.getAttribute('aria-autocomplete') || '').toLowerCase();
        const expandedAttr = element.getAttribute('aria-expanded');
        const activeDescendantId = element.getAttribute('aria-activedescendant');
        const activeDescendant = activeDescendantId
            ? document.getElementById(activeDescendantId)
            : null;

        let controlKind = 'interactive';
        if (tag === 'select') {
            controlKind = 'native-select';
        } else if (
            role === 'combobox' ||
            role === 'listbox' ||
            hasPopup === 'listbox' ||
            hasPopup === 'menu'
        ) {
            controlKind = 'custom-dropdown';
        } else if (tag === 'textarea') {
            controlKind = 'textarea';
        } else if (tag === 'button' || role === 'button') {
            controlKind = 'button';
        } else if (tag === 'a' || role === 'link') {
            controlKind = 'link';
        } else if (tag === 'input') {
            if (type === 'checkbox' || type === 'radio') {
                controlKind = type;
            } else if (type) {
                controlKind = 'input-' + type;
            } else {
                controlKind = 'input';
            }
        } else if (role) {
            controlKind = role;
        }

        const details = {
            control_kind: controlKind,
            expanded: expandedAttr === null ? null : expandedAttr === 'true',
            has_popup: hasPopup || null,
            autocomplete: autocomplete || null,
            selected_text: null,
            options: [],
        };

        if (tag === 'select') {
            details.selected_text = safeText(
                Array.from(element.selectedOptions || [])
                    .map(option => normalizeSpace(option.textContent))
                    .filter(Boolean)
                    .join(', '),
                120
            ) || null;
            details.options = collectOptionLikeEntries(element, 12);
        } else if (controlKind === 'custom-dropdown') {
            details.selected_text = getElementText(
                activeDescendant || element,
                120
            ) || null;
            details.options = collectOptionLikeEntries(element, 12);
        }

        return details;
    }

    function collectFormFields(formElement) {
        const fields = [];
        formElement.querySelectorAll(
            'input, select, textarea, button, [role="combobox"], [role="listbox"], ' +
            '[aria-haspopup="listbox"], [aria-haspopup="menu"]'
        ).forEach((element, index) => {
            if (index >= 25) return;
            fields.push({
                tag: element.tagName.toLowerCase(),
                type: element.type || null,
                name: element.name || null,
                id: element.id || null,
                locator: getLocator(element),
                placeholder: element.placeholder || null,
                required: element.required || false,
                value: safeText(element.value, 120) || null,
                label: element.labels && element.labels.length > 0
                    ? safeText(element.labels[0].textContent, 120)
                    : null,
                role: element.getAttribute('role') || null,
                ...describeControl(element),
            });
        });
        return fields;
    }

    function classifyBlocker(container) {
        const context = [
            container.id || '',
            container.className || '',
            container.getAttribute('role') || '',
            container.getAttribute('aria-label') || '',
            container.innerText || '',
        ].join(' ').toLowerCase();
        if (/cookie|consent|privacy|gdpr/.test(context)) return 'cookie/consent';
        if (/newsletter|subscribe|marketing/.test(context)) return 'newsletter';
        if (/tutorial|tour|onboarding|coach|welcome/.test(context)) return 'tutorial';
        if (/update|upgrade|install/.test(context)) return 'update';
        if (/permission|notification|location|camera|microphone/.test(context)) return 'permission';
        return 'modal/popup';
    }

    function classifyBlockerAction(label, context) {
        const labelLower = (label || '').toLowerCase();
        const contextLower = (context || '').toLowerCase();
        if (
            /accept all|allow all|accept cookies|allow cookies|accept|allow|i agree|agree/.test(labelLower) &&
            /cookie|consent|privacy|gdpr/.test(contextLower)
        ) {
            return { kind: 'accept', score: 150 };
        }
        if (
            /allow|enable|continue/.test(labelLower) &&
            /permission|notification|location|camera|microphone/.test(contextLower)
        ) {
            return { kind: 'allow', score: 130 };
        }
        if (
            /skip|not now|later|no thanks|dismiss|close|got it|ok|okay/.test(labelLower)
        ) {
            return { kind: 'dismiss', score: 125 };
        }
        if (
            /continue|next|start/.test(labelLower) &&
            /tutorial|tour|onboarding|welcome/.test(contextLower)
        ) {
            return { kind: 'continue', score: 115 };
        }
        if (
            /close|dismiss|ok|okay/.test(labelLower) &&
            /modal|popup|dialog|banner|overlay/.test(contextLower)
        ) {
            return { kind: 'dismiss', score: 110 };
        }
        return null;
    }

    function collectBlockerActions(container) {
        const context = [
            container.id || '',
            container.className || '',
            container.getAttribute('role') || '',
            container.getAttribute('aria-label') || '',
            container.innerText || '',
        ].join(' ');
        const actions = [];
        const seen = new Set();
        container.querySelectorAll(
            'button, a, input[type="button"], input[type="submit"], [role="button"]'
        ).forEach(element => {
            if (actions.length >= 8 || !isVisible(element)) return;
            const label = safeText(
                element.innerText || element.textContent || element.value ||
                element.getAttribute('aria-label') || element.title || '',
                80
            );
            if (!label) return;
            const key = label.toLowerCase();
            if (seen.has(key)) return;
            const classification = classifyBlockerAction(label, context);
            const locator = getLocator(element);
            if (!classification || !locator) return;
            seen.add(key);
            actions.push({
                label: label,
                locator: locator,
                kind: classification.kind,
                score: classification.score,
            });
        });
        actions.sort((a, b) => b.score - a.score);
        return actions;
    }

    function collectHeadingsFromDocument(doc, limit) {
        const headings = [];
        doc.querySelectorAll('h1, h2, h3').forEach((heading, index) => {
            if (index >= limit) return;
            const text = safeText(heading.textContent, 100);
            if (text) {
                headings.push({ level: heading.tagName, text: text });
            }
        });
        return headings;
    }

    function classifyLoadingIndicator(element) {
        if (!element || !isVisible(element)) return null;
        const role = (element.getAttribute('role') || '').toLowerCase();
        const ariaBusy = (element.getAttribute('aria-busy') || '').toLowerCase();
        const text = safeText(
            element.innerText || element.textContent || element.getAttribute('aria-label') || '',
            120
        );
        const textLower = text.toLowerCase();
        const context = [
            element.id || '',
            element.className || '',
            role,
            element.getAttribute('aria-label') || '',
            element.getAttribute('data-testid') || '',
            element.getAttribute('name') || '',
            text,
        ].join(' ').toLowerCase();
        const tag = element.tagName.toLowerCase();
        const signals = [];

        if (ariaBusy === 'true') signals.push('aria-busy=true');
        if (role === 'progressbar') signals.push('role=progressbar');
        if (tag === 'progress') signals.push('<progress>');
        if (/(spinner|loading|loader|busy|progress|pending|skeleton|shimmer)/.test(context)) {
            signals.push('loading-related id/class/text');
        }
        if (
            /(loading|please wait|fetching|processing|saving|submitting|syncing|initializing|loading more)/
                .test(textLower)
        ) {
            signals.push('loading text');
        }

        if (!signals.length) return null;

        let kind = 'loading';
        if (/skeleton|shimmer/.test(context)) {
            kind = 'skeleton';
        } else if (role === 'progressbar' || tag === 'progress' || /progress/.test(context)) {
            kind = 'progress';
        } else if (/spinner|loader/.test(context)) {
            kind = 'spinner';
        }

        return {
            kind: kind,
            locator: getLocator(element),
            tag: tag,
            role: role || null,
            id: element.id || null,
            class: element.className ? String(element.className).substring(0, 120) : null,
            text: text || null,
            signals: signals,
        };
    }

    function collectLoadingIndicators(doc, limit) {
        const indicators = [];
        const seen = new Set();
        const candidateSelectors = [
            '[aria-busy="true"]',
            '[role="progressbar"]',
            'progress',
            '[id*="loading"]',
            '[class*="loading"]',
            '[id*="loader"]',
            '[class*="loader"]',
            '[id*="spinner"]',
            '[class*="spinner"]',
            '[id*="progress"]',
            '[class*="progress"]',
            '[id*="busy"]',
            '[class*="busy"]',
            '[id*="skeleton"]',
            '[class*="skeleton"]',
            '[id*="shimmer"]',
            '[class*="shimmer"]',
            '[aria-label]',
            '[data-testid]',
        ];

        doc.querySelectorAll(candidateSelectors.join(', ')).forEach(element => {
            if (indicators.length >= limit || seen.has(element)) return;
            seen.add(element);
            const indicator = classifyLoadingIndicator(element);
            if (!indicator) return;
            indicators.push(indicator);
        });

        indicators.sort((a, b) => {
            const aScore = (a.signals || []).length + (a.kind === 'spinner' ? 1 : 0);
            const bScore = (b.signals || []).length + (b.kind === 'spinner' ? 1 : 0);
            return bScore - aScore;
        });
        return indicators.slice(0, limit);
    }

    function countInteractiveElements(doc, limit) {
        const seen = new Set();
        let count = 0;
        const selectors = [
            'a[href]',
            'button',
            'input',
            'select',
            'textarea',
            '[role="combobox"]',
            '[role="listbox"]',
            '[role="button"]',
            '[role="link"]',
            '[role="tab"]',
            '[role="menuitem"]',
            '[aria-haspopup="listbox"]',
            '[aria-haspopup="menu"]',
            '[onclick]',
            '[tabindex]',
        ];
        selectors.forEach(selector => {
            doc.querySelectorAll(selector).forEach(element => {
                if (count >= limit || seen.has(element) || !isVisible(element)) {
                    return;
                }
                seen.add(element);
                count += 1;
            });
        });
        return count;
    }

    function summarizeFrameDocument(frameElement) {
        const info = {
            same_origin_accessible: false,
            document_title: null,
            document_url: null,
            text_preview: null,
            interactive_elements: 0,
            forms: 0,
            headings: [],
            child_frames: 0,
            access_error: null,
        };

        try {
            const frameWindow = frameElement.contentWindow || null;
            const frameDocument = frameElement.contentDocument || (
                frameWindow ? frameWindow.document : null
            );
            if (!frameDocument) {
                info.access_error = 'frame document unavailable';
                return info;
            }
            info.same_origin_accessible = true;
            info.document_title = frameDocument.title || 'Untitled';
            try {
                info.document_url = frameWindow && frameWindow.location
                    ? String(frameWindow.location.href || '')
                    : null;
            } catch (locationError) {
                info.document_url = null;
            }
            info.text_preview = safeText(
                frameDocument.body ? frameDocument.body.innerText : '',
                180
            ) || null;
            info.interactive_elements = countInteractiveElements(frameDocument, 200);
            info.forms = frameDocument.querySelectorAll('form').length;
            info.headings = collectHeadingsFromDocument(frameDocument, 5);
            info.child_frames = frameDocument.querySelectorAll('iframe, frame').length;
            return info;
        } catch (error) {
            info.access_error = 'cross-origin or inaccessible';
            return info;
        }
    }

    function collectFrameInventory(doc, frames, depth, pathPrefix) {
        const frameNodes = Array.from(doc.querySelectorAll('iframe, frame'));
        frameNodes.forEach((frameElement, index) => {
            if (frames.length >= 25) return;
            const path = pathPrefix ? pathPrefix + '.' + (index + 1) : String(index + 1);
            const frameInfo = {
                path: path,
                depth: depth,
                tag: frameElement.tagName.toLowerCase(),
                locator: getLocator(frameElement),
                id: frameElement.id || null,
                name: frameElement.getAttribute('name') || null,
                title: frameElement.getAttribute('title') || null,
                src: frameElement.getAttribute('src') || null,
                visible: isVisible(frameElement),
            };
            const summary = summarizeFrameDocument(frameElement);
            Object.assign(frameInfo, summary);
            frames.push(frameInfo);

            if (
                frameInfo.same_origin_accessible &&
                depth < 2 &&
                frameInfo.child_frames > 0
            ) {
                try {
                    collectFrameInventory(
                        frameElement.contentDocument,
                        frames,
                        depth + 1,
                        path
                    );
                } catch (nestedError) {
                    frameInfo.access_error = frameInfo.access_error || 'nested frame inspection failed';
                }
            }
        });
    }

    const snapshot = {
        title: document.title || 'Untitled',
        url: window.location.href,
        document_ready_state: document.readyState || 'unknown',
        text: document.body ? document.body.innerText.substring(0, 5000) : '',
        interactive_elements: [],
        headings: [],
        forms: [],
        nav_items: [],
        main_sections: [],
        links: [],
        frames: [],
        possible_blockers: [],
        loading_indicators: [],
        browser_errors: [],
    };

    const interactiveSelectors = [
        'a[href]',
        'button',
        'input',
        'select',
        'textarea',
        '[role="combobox"]',
        '[role="listbox"]',
        '[role="button"]',
        '[role="link"]',
        '[role="tab"]',
        '[role="menuitem"]',
        '[aria-haspopup="listbox"]',
        '[aria-haspopup="menu"]',
        '[onclick]',
        '[tabindex]',
    ];
    const seen = new Set();
    interactiveSelectors.forEach(selector => {
        document.querySelectorAll(selector).forEach(element => {
            if (snapshot.interactive_elements.length >= 100 || seen.has(element) || !isVisible(element)) {
                return;
            }
            seen.add(element);
            snapshot.interactive_elements.push({
                tag: element.tagName.toLowerCase(),
                type: element.type || null,
                id: element.id || null,
                name: element.name || null,
                text: safeText(element.textContent, 100),
                value: safeText(element.value, 120) || null,
                placeholder: element.placeholder || null,
                href: element.href || null,
                'aria-label': element.getAttribute('aria-label'),
                'data-testid': element.getAttribute('data-testid'),
                role: element.getAttribute('role'),
                disabled: element.disabled || false,
                class: element.className ? String(element.className).substring(0, 80) : null,
                locator: getLocator(element),
                ...describeControl(element),
            });
        });
    });

    document.querySelectorAll('h1, h2, h3').forEach((heading, index) => {
        if (index >= 50) return;
        const text = safeText(heading.textContent, 100);
        if (text) {
            snapshot.headings.push({ level: heading.tagName, text: text });
        }
    });

    document.querySelectorAll('form').forEach((formElement, index) => {
        if (index >= 10) return;
        const inputs = formElement.querySelectorAll(
            'input, select, textarea, [role="combobox"], [role="listbox"], ' +
            '[aria-haspopup="listbox"], [aria-haspopup="menu"]'
        );
        snapshot.forms.push({
            index: index,
            id: formElement.id || null,
            locator: getLocator(formElement),
            action: formElement.action || null,
            method: formElement.method || 'get',
            fields: inputs.length,
            form_fields: collectFormFields(formElement),
        });
    });

    document.querySelectorAll('nav a, [role="navigation"] a').forEach((link, index) => {
        if (index >= 40) return;
        const text = safeText(link.textContent, 50);
        if (text) {
            snapshot.nav_items.push({ text: text, href: link.href });
        }
    });

    document.querySelectorAll('main, [role="main"], article, section').forEach((section, index) => {
        if (index >= 30) return;
        snapshot.main_sections.push({
            tag: section.tagName.toLowerCase(),
            id: section.id || null,
            role: section.getAttribute('role'),
            preview: safeText(section.textContent, 100),
        });
    });

    document.querySelectorAll('a[href]').forEach((link, index) => {
        if (index >= 50) return;
        const text = safeText(link.textContent, 80);
        if (text && link.href) {
            snapshot.links.push({ text: text, href: link.href });
        }
    });

    collectFrameInventory(document, snapshot.frames, 0, '');

    const blockerSelectors = [
        'dialog',
        '[role="dialog"]',
        '[aria-modal="true"]',
        '[id*="cookie"]',
        '[class*="cookie"]',
        '[id*="consent"]',
        '[class*="consent"]',
        '[id*="modal"]',
        '[class*="modal"]',
        '[id*="popup"]',
        '[class*="popup"]',
        '[id*="banner"]',
        '[class*="banner"]',
        '[id*="overlay"]',
        '[class*="overlay"]',
        '[id*="newsletter"]',
        '[class*="newsletter"]',
    ].join(', ');
    const blockerContainers = [];
    document.querySelectorAll(blockerSelectors).forEach(container => {
        if (!isVisible(container) || blockerContainers.includes(container)) return;
        blockerContainers.push(container);
    });
    blockerContainers.slice(0, 12).forEach(container => {
        const actions = collectBlockerActions(container);
        if (!actions.length) return;
        snapshot.possible_blockers.push({
            category: classifyBlocker(container),
            preview: safeText(container.innerText, 180),
            actions: actions,
        });
    });

    snapshot.loading_indicators = collectLoadingIndicators(document, 12);

    return snapshot;
    """
    try:
        result = driver.execute_script(js_code)
        if isinstance(result, dict):
            return result
        return json.loads(result)
    except Exception as exc:
        logger.warning("Complex page snapshot failed, using fallback snapshot: %s", exc)
        return _build_fallback_page_snapshot(driver, exc)


def _empty_page_snapshot() -> Dict[str, Any]:
    return {
        "title": "Untitled",
        "url": "unknown",
        "document_ready_state": "unknown",
        "text": "",
        "interactive_elements": [],
        "headings": [],
        "forms": [],
        "nav_items": [],
        "main_sections": [],
        "links": [],
        "frames": [],
        "possible_blockers": [],
        "loading_indicators": [],
        "browser_errors": [],
    }


def _build_fallback_page_snapshot(driver, error: Exception) -> Dict[str, Any]:
    snapshot = _empty_page_snapshot()
    snapshot["title"] = getattr(driver, "title", None) or "Untitled"
    snapshot["url"] = getattr(driver, "current_url", None) or "unknown"
    snapshot["browser_errors"].append(f"snapshot_fallback: {error}")

    try:
        text = driver.execute_script(
            "return document.body ? (document.body.innerText || '').substring(0, 5000) : '';"
        )
        if isinstance(text, str):
            snapshot["text"] = text
    except Exception as text_error:
        logger.debug("Fallback page text extraction failed: %s", text_error)

    return snapshot


def _get_page_snapshot_data(force_refresh: bool = False) -> Dict[str, Any]:
    sl = _get_selenium()
    driver = sl.driver
    cache_key = _get_snapshot_cache_key(driver)
    if force_refresh or cache_key not in _PAGE_SNAPSHOT_CACHE:
        _PAGE_SNAPSHOT_CACHE[cache_key] = _build_page_snapshot(driver)
    return _PAGE_SNAPSHOT_CACHE[cache_key]


def _format_interactive_elements(elements) -> str:
    summary_lines = [f"Found {len(elements)} interactive elements:"]
    for index, element in enumerate(elements, 1):
        locator = element.get("locator", "no-locator")
        tag = element.get("tag", "?")
        text = element.get("text", "")[:50]
        element_type = element.get("type", "")
        description = f"  {index}. <{tag}"
        if element_type:
            description += f" type={element_type}"
        description += f"> locator={locator}"
        control_kind = element.get("control_kind")
        if control_kind:
            description += f" kind={control_kind}"
        if text:
            description += f' text="{text}"'
        selected_text = element.get("selected_text")
        if selected_text:
            description += f' selected="{selected_text[:50]}"'
        options = element.get("options") or []
        if options:
            option_preview = ", ".join(
                option.get("text") or option.get("value") or "?"
                for option in options[:4]
            )
            if option_preview:
                description += f" options=[{option_preview[:80]}]"
        summary_lines.append(description)
    return "\n".join(summary_lines)


def _format_page_structure(snapshot: Dict[str, Any]) -> str:
    lines = [
        f"Page: {snapshot.get('title', 'Untitled')}",
        f"URL: {snapshot.get('url', 'unknown')}",
        "",
        f"Headings ({len(snapshot.get('headings', []))}):",
    ]
    for heading in snapshot.get("headings", []):
        lines.append(f"  {heading['level']}: {heading['text']}")
    lines.append(f"\nForms ({len(snapshot.get('forms', []))}):")
    for form in snapshot.get("forms", []):
        lines.append(
            f"  Form #{form['index']}: id={form['id']}, method={form['method']}, fields={form['fields']}"
        )
    lines.append(f"\nNavigation ({len(snapshot.get('nav_items', []))}):")
    for nav_item in snapshot.get("nav_items", [])[:20]:
        lines.append(f"  {nav_item['text']} → {nav_item['href']}")
    frames = snapshot.get("frames", [])
    lines.append(f"\nFrames ({len(frames)}):")
    if frames:
        for frame in frames[:10]:
            locator = frame.get("locator") or "no-locator"
            status = "same-origin" if frame.get("same_origin_accessible") else "cross-origin/inaccessible"
            label_parts = [f"path={frame.get('path', '?')}", f"locator={locator}", status]
            title = frame.get("title") or frame.get("document_title")
            if title:
                label_parts.append(f'title="{title[:50]}"')
            lines.append("  " + ", ".join(label_parts))
    else:
        lines.append("  none")
    return "\n".join(lines)


def _format_possible_blockers(blockers) -> list[str]:
    if not blockers:
        return ["Possible blockers: none"]
    lines = [f"Possible blockers ({len(blockers)}):"]
    for blocker in blockers[:5]:
        action_labels = ", ".join(
            action.get("label", "?")
            for action in blocker.get("actions", [])[:4]
        ) or "no actions found"
        lines.append(
            f"  - {blocker.get('category', 'unknown')}: "
            f"{blocker.get('preview', '')[:80]} "
            f"(actions: {action_labels})"
        )
    return lines


def _format_loading_indicators(snapshot: Dict[str, Any]) -> list[str]:
    ready_state = snapshot.get("document_ready_state", "unknown")
    indicators = snapshot.get("loading_indicators", [])
    if not indicators:
        return [f"Loading indicators: none detected (readyState={ready_state})"]
    lines = [f"Loading indicators ({len(indicators)}) (readyState={ready_state}):"]
    for indicator in indicators[:5]:
        details = [indicator.get("kind", "loading")]
        locator = indicator.get("locator")
        if locator:
            details.append(f"locator={locator}")
        role = indicator.get("role")
        if role:
            details.append(f"role={role}")
        text = indicator.get("text")
        if text:
            details.append(f'text="{text[:60]}"')
        signals = indicator.get("signals") or []
        if signals:
            details.append("signals=" + ", ".join(signals[:3]))
        lines.append("  - " + ", ".join(details))
    return lines


def _format_frames(frames) -> list[str]:
    if not frames:
        return ["Frames: none detected"]
    lines = [f"Frames ({len(frames)}):"]
    for frame in frames[:25]:
        locator = frame.get("locator") or "no-locator"
        status = "same-origin" if frame.get("same_origin_accessible") else "cross-origin/inaccessible"
        primary = [
            f"path={frame.get('path', '?')}",
            f"depth={frame.get('depth', 0)}",
            f"locator={locator}",
            status,
        ]
        frame_id = frame.get("id")
        frame_name = frame.get("name")
        frame_title = frame.get("title") or frame.get("document_title")
        frame_src = frame.get("src") or frame.get("document_url")
        if frame_id:
            primary.append(f"id={frame_id}")
        if frame_name:
            primary.append(f"name={frame_name}")
        if frame_title:
            primary.append(f'title="{frame_title[:50]}"')
        if frame_src:
            primary.append(f"src={frame_src[:80]}")
        lines.append("  - " + ", ".join(primary))

        secondary = []
        if frame.get("same_origin_accessible"):
            secondary.append(
                f"interactive={int(frame.get('interactive_elements', 0))}"
            )
            secondary.append(f"forms={int(frame.get('forms', 0))}")
            secondary.append(f"child_frames={int(frame.get('child_frames', 0))}")
            headings = frame.get("headings", [])
            if headings:
                secondary.append(
                    "headings=" + ", ".join(
                        heading.get("text", "")[:30] for heading in headings[:3] if heading.get("text")
                    )
                )
            text_preview = frame.get("text_preview")
            if text_preview:
                secondary.append(f'text="{text_preview[:80]}"')
        else:
            access_error = frame.get("access_error")
            if access_error:
                secondary.append(access_error)
        if secondary:
            lines.append("    " + " | ".join(secondary))
    return lines


def _resolve_form_fields(snapshot: Dict[str, Any], form_locator: str):
    forms = snapshot.get("forms", [])
    if not forms:
        return []
    if not form_locator or form_locator == "css=form":
        return forms[0].get("form_fields", [])
    if form_locator.startswith("id="):
        form_id = form_locator[3:]
        for form in forms:
            if form.get("id") == form_id:
                return form.get("form_fields", [])
    return None


@tool
def get_page_snapshot(refresh: bool = False) -> str:
    """Gets a cached combined snapshot of the current page."""
    snapshot = _get_page_snapshot_data(force_refresh=bool(refresh))
    lines = [
        f"Page: {snapshot.get('title', 'Untitled')}",
        f"URL: {snapshot.get('url', 'unknown')}",
        f"Document readyState: {snapshot.get('document_ready_state', 'unknown')}",
        f"Interactive elements: {len(snapshot.get('interactive_elements', []))}",
        f"Forms: {len(snapshot.get('forms', []))}",
        f"Links: {len(snapshot.get('links', []))}",
        f"Frames: {len(snapshot.get('frames', []))}",
        "",
        "Headings:",
    ]
    headings = snapshot.get("headings", [])[:10]
    if headings:
        for heading in headings:
            lines.append(f"  {heading['level']}: {heading['text']}")
    else:
        lines.append("  none")
    lines.append("")
    lines.append("Text preview:")
    lines.append(snapshot.get("text", "")[:500] or "<empty>")
    lines.append("")
    lines.extend(_format_frames(snapshot.get("frames", [])[:5]))
    lines.append("")
    lines.extend(_format_loading_indicators(snapshot))
    lines.append("")
    lines.extend(_format_possible_blockers(snapshot.get("possible_blockers", [])))
    return "\n".join(lines)


@tool
def get_loading_state(refresh: bool = False) -> str:
    """Gets automatically detected loading indicators from the current page."""
    snapshot = _get_page_snapshot_data(force_refresh=bool(refresh))
    return "\n".join(_format_loading_indicators(snapshot))


@tool
def get_interactive_elements() -> str:
    """Extracts all interactive elements from the current page.

    Finds buttons, links, inputs, selects, textareas, and elements
    with click handlers. Returns structured data the agent can use
    to decide what to interact with.

    Returns:
        JSON-formatted list of interactive elements with their locators,
        types, text, and attributes.
    """
    snapshot = _get_page_snapshot_data()
    return _format_interactive_elements(snapshot.get("interactive_elements", []))


@tool
def get_page_structure() -> str:
    """Gets a high-level structural overview of the current page.

    Returns headings, main landmarks, forms, and navigation elements
    to help the agent understand page layout.

    Returns:
        Structured overview of the page.
    """
    snapshot = _get_page_snapshot_data()
    return _format_page_structure(snapshot)


@tool
def get_page_text_content() -> str:
    """Gets the visible text content of the current page.

    Returns:
        The visible text content (truncated for large pages).
    """
    snapshot = _get_page_snapshot_data()
    text = snapshot.get("text", "")
    if text and len(text) > 5000:
        text = text[:5000] + "\n... [truncated]"
    return f"Page text content:\n{text}"


@tool
def get_element_count(locator: str) -> str:
    """Counts the number of elements matching a locator.

    Args:
        locator: CSS selector or XPath to count.

    Returns:
        The count of matching elements.
    """
    sl = _get_selenium()
    count = sl.get_element_count(locator)
    return f"Found {count} elements matching: {locator}"


@tool
def get_all_links() -> str:
    """Gets all links on the current page with their text and URLs.

    Returns:
        List of links with their text and href attributes.
    """
    snapshot = _get_page_snapshot_data()
    links = snapshot.get("links", [])
    lines = [f"Found {len(links)} links:"]
    for index, link in enumerate(links, 1):
        lines.append(f"  {index}. [{link['text']}] → {link['href']}")
    return "\n".join(lines)


@tool
def get_frame_inventory(refresh: bool = False) -> str:
    """Gets an inventory of iframe/frame contexts on the current page.

    Returns visible locator information plus same-origin summaries when
    the frame document is accessible from the current browsing context.
    """
    snapshot = _get_page_snapshot_data(force_refresh=bool(refresh))
    return "\n".join(_format_frames(snapshot.get("frames", [])))


@tool
def get_form_fields(form_locator: str = "css=form") -> str:
    """Gets all input fields within a form element.

    Args:
        form_locator: Locator for the form element (defaults to first form).

    Returns:
        List of form fields with their types, names, and attributes.
    """
    snapshot = _get_page_snapshot_data()
    fields = _resolve_form_fields(snapshot, form_locator)
    if fields is None:
        sl = _get_selenium()
        driver = sl.driver
        css = form_locator
        if form_locator.startswith("css="):
            css = form_locator[4:]
        elif form_locator.startswith("id="):
            css = f"#{form_locator[3:]}"
        css_literal = json.dumps(css)

        js_code = f"""
        const form = document.querySelector({css_literal});
        if (!form) return JSON.stringify([]);
        function normalizeSpace(value) {{
            return String(value || '').replace(/\\s+/g, ' ').trim();
        }}
        function getElementText(element, limit) {{
            if (!element) return '';
            return normalizeSpace(
                (element.innerText || element.textContent ||
                    element.getAttribute('aria-label') || element.value || '')
            ).substring(0, limit);
        }}
        function collectOptions(element, limit) {{
            if (!element) return [];
            if (element.tagName && element.tagName.toLowerCase() === 'select') {{
                return Array.from(element.options || []).slice(0, limit).map(option => ({{
                    text: getElementText(option, 80) || null,
                    value: normalizeSpace(option.value || option.getAttribute('value') || '').substring(0, 80) || null,
                    selected: option.selected || false,
                    disabled: option.disabled || false,
                }}));
            }}
            return [];
        }}
        const fields = [];
        form.querySelectorAll(
            'input, select, textarea, button, [role="combobox"], [role="listbox"], ' +
            '[aria-haspopup="listbox"], [aria-haspopup="menu"]'
        ).forEach(el => {{
            const tag = el.tagName.toLowerCase();
            const role = (el.getAttribute('role') || '').toLowerCase();
            const hasPopup = (el.getAttribute('aria-haspopup') || '').toLowerCase();
            let controlKind = 'interactive';
            if (tag === 'select') {{
                controlKind = 'native-select';
            }} else if (role === 'combobox' || role === 'listbox' || hasPopup === 'listbox' || hasPopup === 'menu') {{
                controlKind = 'custom-dropdown';
            }} else if (tag === 'input') {{
                controlKind = el.type ? 'input-' + el.type.toLowerCase() : 'input';
            }} else if (tag === 'textarea') {{
                controlKind = 'textarea';
            }} else if (tag === 'button') {{
                controlKind = 'button';
            }}
            fields.push({{
                tag: tag,
                type: el.type || null,
                name: el.name || null,
                id: el.id || null,
                placeholder: el.placeholder || null,
                required: el.required || false,
                value: el.value || null,
                label: el.labels && el.labels.length > 0 ? el.labels[0].textContent.trim() : null,
                role: role || null,
                control_kind: controlKind,
                selected_text: tag === 'select'
                    ? Array.from(el.selectedOptions || [])
                        .map(option => getElementText(option, 80))
                        .filter(Boolean)
                        .join(', ') || null
                    : null,
                options: collectOptions(el, 12),
            }});
        }});
        return JSON.stringify(fields);
        """
        fields = json.loads(driver.execute_script(js_code))

    lines = [f"Form fields ({len(fields)}):"]
    for field in fields:
        name = field.get("name") or field.get("id") or "unnamed"
        field_type = field.get("type") or field.get("tag")
        control_kind = field.get("control_kind")
        if control_kind and control_kind not in {field_type, field.get("tag")}:
            field_type = f"{field_type}/{control_kind}"
        label = field.get("label") or field.get("placeholder") or ""
        required = " [REQUIRED]" if field.get("required") else ""
        lines.append(f"  - {name} ({field_type}){required}: {label}")
        selected_text = field.get("selected_text")
        if selected_text:
            lines.append(f"    selected: {selected_text[:80]}")
        options = field.get("options") or []
        if options:
            option_preview = ", ".join(
                option.get("text") or option.get("value") or "?"
                for option in options[:6]
            )
            if option_preview:
                lines.append(f"    options: {option_preview[:120]}")
    return "\n".join(lines)


@tool
def check_page_errors() -> str:
    """Checks for JavaScript console errors and failed network requests.

    Returns:
        List of errors found or 'No errors detected'.
    """
    sl = _get_selenium()
    driver = sl.driver

    try:
        logs = driver.get_log("browser")
        errors = [log for log in logs if log.get("level") in ("SEVERE", "ERROR")]
        if errors:
            lines = [f"Found {len(errors)} browser errors:"]
            for err in errors[:20]:
                lines.append(f"  [{err.get('level')}] {err.get('message', '')[:200]}")
            return "\n".join(lines)
        return "No browser console errors detected"
    except Exception:
        return "Unable to retrieve browser console logs (may not be supported by the driver)"


# ---------------------------------------------------------------------------
# Tool list export
# ---------------------------------------------------------------------------

BROWSER_ANALYSIS_TOOLS = instrument_tool_list([
    get_page_snapshot,
    get_loading_state,
    get_interactive_elements,
    get_page_structure,
    get_page_text_content,
    get_element_count,
    get_all_links,
    get_frame_inventory,
    get_form_fields,
    check_page_errors,
])
