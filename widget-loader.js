// Import the widget
import { InteractiveDocumentWidget } from './widget.js';
 
// Create a global function to open the widget
window.openInteractiveDocumentWidget = function(config = {}) {
    new InteractiveDocumentWidget(config);
};

// Create a simple event hub for widget communication
window.widgetEventHub = new EventTarget(); 