/* eslint-disable */
/* Auto-generated placeholder for PowerApps Component Framework manifest types. */

export interface IInputs {
  oldPdfBase64: ComponentFramework.PropertyTypes.MultilineTextProperty;
  newPdfBase64: ComponentFramework.PropertyTypes.MultilineTextProperty;
  dpi: ComponentFramework.PropertyTypes.WholeNumberProperty;
  gridRows: ComponentFramework.PropertyTypes.WholeNumberProperty;
  gridCols: ComponentFramework.PropertyTypes.WholeNumberProperty;
  diffThreshold: ComponentFramework.PropertyTypes.WholeNumberProperty;
  minRegionArea: ComponentFramework.PropertyTypes.WholeNumberProperty;
  strokeWidthPt: ComponentFramework.PropertyTypes.DecimalNumberProperty;
  overlayAlpha: ComponentFramework.PropertyTypes.DecimalNumberProperty;
  colorRemoved: ComponentFramework.PropertyTypes.StringProperty;
  colorAdded: ComponentFramework.PropertyTypes.StringProperty;
  runCompare: ComponentFramework.PropertyTypes.TwoOptionsProperty;
  outputPdfBase64: ComponentFramework.PropertyTypes.MultilineTextProperty;
  diffSummaryJson: ComponentFramework.PropertyTypes.MultilineTextProperty;
  diffCount: ComponentFramework.PropertyTypes.WholeNumberProperty;
  status: ComponentFramework.PropertyTypes.MultilineTextProperty;
}

export interface IOutputs {
  outputPdfBase64?: string | null;
  diffSummaryJson?: string | null;
  diffCount?: number | null;
  status?: string | null;
}
