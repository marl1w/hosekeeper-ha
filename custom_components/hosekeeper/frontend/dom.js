/**
 * Minimal DOM helpers.
 *
 * The panel is deliberately dependency-free — no build step, no bundler, nothing to
 * install — so these few helpers stand in for a framework.
 */

import { ALIASES, ICONS } from "./icons.js";

/** Create an element with attributes, listeners and children. */
export function el(tag, props = {}, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(props)) {
    if (value === null || value === undefined || value === false) continue;
    if (key === "class") node.className = value;
    else if (key === "text") node.textContent = value;
    else if (key === "dataset") Object.assign(node.dataset, value);
    else if (key === "style" && typeof value === "object") Object.assign(node.style, value);
    else if (key.startsWith("on") && typeof value === "function") {
      node.addEventListener(key.slice(2).toLowerCase(), value);
    } else if (value === true) node.setAttribute(key, "");
    else node.setAttribute(key, String(value));
  }
  append(node, children);
  return node;
}

/** Append a nested array of children, skipping empties. */
export function append(parent, children) {
  for (const child of children.flat(Infinity)) {
    if (child === null || child === undefined || child === false) continue;
    parent.append(child instanceof Node ? child : document.createTextNode(String(child)));
  }
  return parent;
}

/** Replace all children of a node. */
export function clear(node) {
  while (node.firstChild) node.removeChild(node.firstChild);
  return node;
}

/** Attach stylesheet text to a shadow root, preferring constructable stylesheets. */
export function adoptStyles(root, cssText) {
  try {
    const sheet = new CSSStyleSheet();
    sheet.replaceSync(cssText);
    root.adoptedStyleSheets = [...root.adoptedStyleSheets, sheet];
    return;
  } catch {
    root.append(el("style", { text: cssText }));
  }
}

/** An icon, drawn from the panel's own set so nothing depends on the icon font. */
export function icon(name, extraClass = "") {
  const key = ALIASES[name] || name.replace(/^mdi:/, "");
  const shapes = ICONS[key] || ICONS.info;
  const node = svg("svg", {
    class: `icon ${extraClass}`.trim(),
    viewBox: "0 0 24 24",
    "aria-hidden": "true",
    focusable: "false",
  });
  for (const { tag, ...attrs } of shapes) node.append(svg(tag, attrs));
  return node;
}

/** SVG element with attributes. */
export function svg(tag, attrs = {}, ...children) {
  const node = document.createElementNS("http://www.w3.org/2000/svg", tag);
  for (const [key, value] of Object.entries(attrs)) {
    if (value === null || value === undefined) continue;
    node.setAttribute(key, String(value));
  }
  append(node, children);
  return node;
}

/** Debounce onto the next animation frame, coalescing bursts of state changes. */
export function frameDebounce(fn) {
  let handle = null;
  return (...args) => {
    if (handle !== null) return;
    handle = requestAnimationFrame(() => {
      handle = null;
      fn(...args);
    });
  };
}
