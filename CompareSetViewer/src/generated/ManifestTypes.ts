/* eslint-disable */
/* Auto-generated placeholder for PowerApps Component Framework manifest types. */

export interface IInputs {
  oldPdfBase64: ComponentFramework.PropertyTypes.MultilineTextProperty;
  newPdfBase64: ComponentFramework.PropertyTypes.MultilineTextProperty;
  dpi: ComponentFramework.PropertyTypes.WholeNumberProperty;
  threshold: ComponentFramework.PropertyTypes.WholeNumberProperty;
  diffPdfBase64: ComponentFramework.PropertyTypes.MultilineTextProperty;
}

export interface IOutputs {
  diffPdfBase64?: string | null;
  statusMessage?: string | null;
  isProcessing?: boolean | null;
}
