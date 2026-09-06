/**
 * Just enough DOM to render the panel's views in Node.
 *
 * The views only ever create elements, set attributes and append children, so a few dozen
 * lines stand in for a browser — and a view that throws does so here, in a test, instead of
 * blanking the page in somebody's sidebar.
 */

class ClassList {
  constructor(node) {
    this.node = node;
  }

  add(...names) {
    const set = new Set((this.node.className || "").split(/\s+/).filter(Boolean));
    for (const n of names) set.add(n);
    this.node.className = [...set].join(" ");
  }

  contains(name) {
    return (this.node.className || "").split(/\s+/).includes(name);
  }

  remove(...names) {
    const gone = new Set(names);
    this.node.className = (this.node.className || "")
      .split(/\s+/)
      .filter((n) => n && !gone.has(n))
      .join(" ");
  }

  toggle(name, force) {
    const on = force === undefined ? !this.contains(name) : Boolean(force);
    if (on) this.add(name);
    else this.remove(name);
    return on;
  }
}

class Node {
  constructor(tag, ns = null) {
    this.tagName = String(tag).toUpperCase();
    this.localName = String(tag);
    this.namespaceURI = ns;
    this.children = [];
    this.attributes = {};
    this.style = {};
    this.dataset = {};
    this.listeners = {};
    this.className = "";
    this._text = "";
    this.hidden = false;
    this.parentNode = null;
  }

  /**
   * `hidden` is an attribute and a property, and a browser keeps the two in step.
   *
   * The panel opens and closes a dialog by setting the property; the markup declares it
   * closed with the attribute. Without this the two were separate facts and a test could
   * only ever see one of them.
   */
  get hidden() {
    return "hidden" in this.attributes;
  }

  set hidden(value) {
    if (value) this.attributes.hidden = "";
    else delete this.attributes.hidden;
  }

  get classList() {
    return new ClassList(this);
  }

  setAttribute(name, value) {
    if (value === undefined) throw new Error(`undefined attribute ${name} on <${this.localName}>`);
    this.attributes[name] = String(value);
    if (name === "class") this.className = String(value);
    // A browser seeds an input's live value from the attribute, and a test that types into
    // a field needs the same, or it can only ever read back what the page rendered.
    if (name === "value") this.value = String(value);
  }

  getAttribute(name) {
    return this.attributes[name] ?? null;
  }

  removeAttribute(name) {
    delete this.attributes[name];
  }

  attachShadow() {
    this.shadowRoot = new Node("#shadow");
    this.shadowRoot.adoptedStyleSheets = [];
    return this.shadowRoot;
  }

  /**
   * Actually dispatch, so a test can press a button and see what it wrote.
   *
   * This used to return true and do nothing, which meant every handler in the panel was
   * unreachable from a test: the views were checked for what they draw and never for what
   * they do when touched.
   */
  dispatchEvent(event = {}) {
    const type = typeof event === "string" ? event : event.type;
    const detail = typeof event === "string" ? { type } : event;
    detail.target ||= this;
    detail.currentTarget = this;
    detail.preventDefault ||= () => {};
    detail.stopPropagation ||= () => {};
    for (const fn of this.listeners[type] || []) fn(detail);
    return true;
  }

  /** Shorthand for the press a person would make. */
  click() {
    return this.dispatchEvent({ type: "click" });
  }

  addEventListener(type, fn) {
    (this.listeners[type] ||= []).push(fn);
  }

  append(...nodes) {
    for (const child of nodes) {
      if (child === null || child === undefined) throw new Error(`appended ${child} to <${this.localName}>`);
      const node = child instanceof Node ? child : new TextNode(String(child));
      node.parentNode = this;
      this.children.push(node);
      // A browser gives a select the value of its first option until something chooses
      // otherwise. Without this a dialog read back as having chosen nothing at all.
      if (this.localName === "select" && node.localName === "option" && this.value === undefined) {
        this.value = node.attributes.value;
      }
    }
  }

  insertBefore(node, ref) {
    const at = ref ? this.children.indexOf(ref) : this.children.length;
    this.children.splice(at < 0 ? this.children.length : at, 0, node);
    node.parentNode = this;
    return node;
  }

  removeChild(node) {
    const at = this.children.indexOf(node);
    if (at >= 0) this.children.splice(at, 1);
    return node;
  }

  remove() {
    this.parentNode?.removeChild(this);
  }

  get firstChild() {
    return this.children[0] || null;
  }

  set textContent(value) {
    this._text = String(value);
    this.children = [];
  }

  get textContent() {
    return this._text + this.children.map((c) => c.textContent).join("");
  }

  /** Depth-first search by class name, for assertions. */
  find(predicate) {
    for (const child of this.children) {
      if (child instanceof Node) {
        if (predicate(child)) return child;
        const deeper = child.find(predicate);
        if (deeper) return deeper;
      }
    }
    return null;
  }

  findAll(predicate, out = []) {
    for (const child of this.children) {
      if (child instanceof Node) {
        if (predicate(child)) out.push(child);
        child.findAll(predicate, out);
      }
    }
    return out;
  }
}

class TextNode extends Node {
  constructor(text) {
    super("#text");
    this._text = text;
  }
}

export function installDom() {
  globalThis.Node = Node;
  const body = new Node("body");
  // A browser upgrades <hosekeeper-panel> to the class that registered the name, and runs
  // its connectedCallback when it lands in the document. A shim that hands back a plain
  // node instead makes every panel look blank, which is a fault in the shim and not in the
  // page — one that cost an afternoon.
  const registry = new Map();
  const create = (tag) => {
    const Klass = registry.get(String(tag).toLowerCase());
    if (!Klass) return new Node(tag);
    const element = new Klass();
    element.localName = String(tag).toLowerCase();
    element.tagName = element.localName.toUpperCase();
    return element;
  };
  body.append = (...nodes) => {
    Node.prototype.append.call(body, ...nodes);
    for (const node of nodes) node?.connectedCallback?.();
  };
  globalThis.document = {
    body,
    createElement: create,
    createElementNS: (ns, tag) => new Node(tag, ns),
    createTextNode: (text) => new TextNode(text),
  };
  globalThis.customElements = {
    get: (name) => registry.get(name),
    define: (name, klass) => registry.set(name, klass),
  };
  globalThis.customElementRegistry = registry;
  globalThis.HTMLElement = Node;
  globalThis.Event = class {
    constructor(type) {
      this.type = type;
    }
  };
  // Deferred, as a browser does it: a synchronous stub makes the panel's frame debounce
  // keep a handle for ever and drop every render after the first.
  let frame = 0;
  globalThis.requestAnimationFrame = (fn) => {
    frame += 1;
    setTimeout(fn, 0);
    return frame;
  };
  globalThis.cancelAnimationFrame = () => {};
  globalThis.localStorage = {
    store: new Map(),
    getItem(key) {
      return this.store.has(key) ? this.store.get(key) : null;
    },
    setItem(key, value) {
      this.store.set(key, String(value));
    },
    removeItem(key) {
      this.store.delete(key);
    },
  };
  globalThis.CSSStyleSheet = class {
    replaceSync() {}
  };
  globalThis.location = { search: "", href: "http://127.0.0.1/" };
  globalThis.window = { innerWidth: 1280, matchMedia: () => ({ matches: false }) };
  return { Node, TextNode };
}

export const byClass = (name) => (node) => node.classList.contains(name);
