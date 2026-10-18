// Closing surfaces may still be visible for a few frames. Escape targets logical
// open dialogs, so a second press can dismiss the parent during that transition.
const stack: { token: symbol; close: () => void }[] = [];
function escape(event: KeyboardEvent) {
  if (
    event.key !== 'Escape' ||
    event.defaultPrevented ||
    document.querySelector('[role="alertdialog"], [role="menu"]')
  )
    return;
  const current = stack.at(-1);
  if (!current) return;
  event.preventDefault();
  event.stopImmediatePropagation();
  current.close();
}
export function registerDialog(close: () => void) {
  const token = Symbol('dialog');
  if (!stack.length) document.addEventListener('keydown', escape, true);
  stack.push({ token, close });
  return () => {
    const i = stack.findIndex((item) => item.token === token);
    if (i >= 0) stack.splice(i, 1);
    if (!stack.length) document.removeEventListener('keydown', escape, true);
  };
}
