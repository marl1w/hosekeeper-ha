/**
 * The shell both of Tracking's dialogs share.
 *
 * A button, a scrim, a card, and Cancel beside the action. It lives inside the page it
 * belongs to rather than being bolted onto the document: the panel is in a shadow root, and
 * a dialog appended anywhere else would lose every style it has.
 *
 * Both callers ask a handful of short questions about one lawn or all of them, and both are
 * things a person does now and then rather than on every visit, which is why they are behind
 * a button instead of laid out inline.
 */

import { el, icon } from "../dom.js";
import { strings } from "../i18n.js";

export const ALL = "__all__";

/** A row in a dialog: what is being asked, and the control that answers it. */
export function field(label, control, { hidden = false } = {}) {
  const row = el("label", { class: "record__field" }, el("span", {}, label), control);
  row.hidden = hidden;
  return row;
}

/** A select of the lawns, with "all of them" first when there is more than one. */
export function lawnChoice(snapshots, { lang, zoneName, id }) {
  const s = strings(lang);
  const many = snapshots.length > 1;
  return el(
    "select",
    { class: "record__select", id },
    many ? el("option", { value: ALL }, s.ui.allZones) : null,
    snapshots.map((snapshot) =>
      el("option", { value: snapshot.zone_id }, snapshot.field?.name || zoneName(snapshot.zone_id))
    )
  );
}

/** The lawns a dialog's answer applies to. */
export function chosen(snapshots, select) {
  return select.value === ALL ? snapshots.map((s) => s.zone_id) : [select.value];
}

/**
 * Build a dialog and the button that opens it.
 *
 * `onOpen` runs each time it is opened, so the controls can be reset to what the lawn
 * currently says rather than to whatever was left there last time.
 */
export function dialog({ lang, title, openLabel, openIcon, submitLabel, body, onOpen, onSubmit }) {
  const s = strings(lang);
  const overlay = el("div", { class: "modal" });
  overlay.hidden = true;
  const close = () => {
    overlay.hidden = true;
  };
  const open = () => {
    onOpen?.();
    overlay.hidden = false;
  };

  overlay.append(
    el("div", { class: "modal__scrim", onClick: close }, ""),
    el(
      "div",
      { class: "modal__card", role: "dialog", "aria-modal": "true", "aria-label": title },
      el("div", { class: "modal__title" }, title),
      ...body,
      el(
        "div",
        { class: "modal__actions" },
        el("button", { class: "rate__btn", onClick: close }, s.ui.cancel),
        el(
          "button",
          {
            class: "rate__btn rate__btn--primary",
            onClick: () => {
              if (onSubmit() === false) return;
              close();
            },
          },
          icon("mdi:check", "icon--sm"),
          submitLabel
        )
      )
    )
  );

  const button = el(
    "button",
    { class: "rate__btn rate__btn--primary", onClick: open },
    icon(openIcon, "icon--sm"),
    openLabel
  );
  return { button, overlay };
}
