import { AllSelection, TextSelection } from '@milkdown/kit/prose/state';

export function synchronizeCommandSelection(view) {
    if (view.composing) return false;
    const current = view.state.selection;
    // Node and table selections have their own semantics, not text-range semantics.
    if (!(current instanceof AllSelection || current instanceof TextSelection)) return true;
    const native = view.dom.ownerDocument.getSelection();
    if (!native?.anchorNode || !native.focusNode) return true;
    const ownsAnchor = view.dom.contains(native.anchorNode);
    const ownsHead = view.dom.contains(native.focusNode);
    if (!ownsAnchor && !ownsHead) return true;
    if (!ownsAnchor || !ownsHead) return false;
    let selection;
    try {
        const anchor = view.posAtDOM(native.anchorNode, native.anchorOffset);
        const head = view.posAtDOM(native.focusNode, native.focusOffset);
        if (anchor === current.anchor && head === current.head) return true;
        selection = TextSelection.between(
            view.state.doc.resolve(anchor), view.state.doc.resolve(head),
        );
    } catch (error) {
        if (error instanceof RangeError) return false;
        throw error;
    }
    if (!selection.eq(current)) view.dispatch(view.state.tr.setSelection(selection));
    return true;
}
