import { app } from "../../../scripts/app.js";

const NODE_NAME = "KeywordWildcardProcessor";
const SELECTOR_PLACEHOLDER = "Select Wildcard";

function findWidget(node, name) {
    return node.widgets?.find((widget) => widget.name === name);
}

function commitWidgetValue(node, widget, value) {
    widget.value = value;

    const index = node.widgets?.indexOf(widget) ?? -1;
    if (index >= 0 && Array.isArray(node.widgets_values)) {
        node.widgets_values[index] = value;
    }

    widget.callback?.(value, app.canvas, node);
    app.graph?.setDirtyCanvas?.(true, true);
}

function appendWildcardToken(node, token) {
    if (!token || token === SELECTOR_PLACEHOLDER) {
        return;
    }

    const promptWidget = findWidget(node, "prompt");
    if (!promptWidget) {
        return;
    }

    const current = String(promptWidget.value ?? "");
    const separator = current.length > 0 && !/\s$/.test(current) ? " " : "";
    commitWidgetValue(node, promptWidget, `${current}${separator}${token}`);
}

function configureSelector(node) {
    const selector = findWidget(node, "wildcard_selector");
    if (!selector || selector.__keywordWildcardConfigured) {
        return;
    }

    selector.__keywordWildcardConfigured = true;
    node.__keywordWildcardSelection = SELECTOR_PLACEHOLDER;

    selector.callback = () => {
        appendWildcardToken(node, node.__keywordWildcardSelection);
    };

    Object.defineProperty(selector, "value", {
        configurable: true,
        get: () => SELECTOR_PLACEHOLDER,
        set: (value) => {
            if (value && value !== SELECTOR_PLACEHOLDER) {
                node.__keywordWildcardSelection = value;
            }
        },
    });

    selector.serializeValue = () => SELECTOR_PLACEHOLDER;
}

function configureTextAreas(node) {
    const promptWidget = findWidget(node, "prompt");
    const processedWidget = findWidget(node, "processed_text");
    const keywordWidget = findWidget(node, "keyword");

    if (promptWidget?.inputEl) {
        promptWidget.inputEl.placeholder = "Prompt or __file_name__";
    }

    if (processedWidget) {
        processedWidget.options = {
            ...(processedWidget.options ?? {}),
            disabled: true,
        };
        if (processedWidget.inputEl) {
            processedWidget.inputEl.placeholder = "Final result (automatically generated)";
            processedWidget.inputEl.disabled = true;
            processedWidget.inputEl.readOnly = true;
        }
    }

    if (keywordWidget?.inputEl) {
        keywordWidget.inputEl.placeholder = "Ex.: 20-year-old man";
    }
}

app.registerExtension({
    name: "Comfy.KeywordWildcardProcessor",

    async beforeRegisterNodeDef(nodeType, nodeData) {
        if (nodeData.name !== NODE_NAME) {
            return;
        }

        const originalOnExecuted = nodeType.prototype.onExecuted;
        nodeType.prototype.onExecuted = function (message) {
            originalOnExecuted?.apply(this, arguments);

            const processedWidget = findWidget(this, "processed_text");
            if (!processedWidget) {
                return;
            }

            const payload = message?.text;
            const text = Array.isArray(payload) ? payload[0] : payload;
            if (typeof text !== "string") {
                return;
            }

            processedWidget.value = text;
            const index = this.widgets?.indexOf(processedWidget) ?? -1;
            if (index >= 0 && Array.isArray(this.widgets_values)) {
                this.widgets_values[index] = text;
            }

            app.graph?.setDirtyCanvas?.(true, true);
        };
    },

    nodeCreated(node) {
        if (node.comfyClass !== NODE_NAME) {
            return;
        }

        configureTextAreas(node);
        configureSelector(node);

        const minimumWidth = 360;
        const minimumHeight = 520;
        node.setSize?.([
            Math.max(node.size?.[0] ?? 0, minimumWidth),
            Math.max(node.size?.[1] ?? 0, minimumHeight),
        ]);
    },
});
