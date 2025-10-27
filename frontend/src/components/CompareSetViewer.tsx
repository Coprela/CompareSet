import { useEffect, useMemo, useState } from "react";
import ThemeToggle from "./ThemeToggle";
import PdfPreview from "./PdfPreview";
import { Theme } from "../hooks/useTheme";

const API_BASE = import.meta.env.VITE_COMPARESET_API ?? "http://localhost:5000";

type CompareMode = "side-by-side" | "overlay";

type CompareSetViewerProps = {
  theme: Theme;
  onToggleTheme: () => void;
};

type Status = "idle" | "uploading" | "processing" | "complete" | "error";

const statusMessages: Record<Status, string> = {
  idle: "Drop your PDFs or choose files to begin.",
  uploading: "Uploading documents…",
  processing: "Generating comparison…",
  complete: "Comparison ready.",
  error: "Comparison failed. Check the details and try again."
};

const CompareSetViewer: React.FC<CompareSetViewerProps> = ({ theme, onToggleTheme }) => {
  const [oldFile, setOldFile] = useState<File | null>(null);
  const [newFile, setNewFile] = useState<File | null>(null);
  const [resultUrl, setResultUrl] = useState<string | null>(null);
  const [resultBlob, setResultBlob] = useState<Blob | null>(null);
  const [previewMode, setPreviewMode] = useState<CompareMode>("side-by-side");
  const [status, setStatus] = useState<Status>("idle");
  const [message, setMessage] = useState<string>(statusMessages.idle);
  const [progress, setProgress] = useState<number>(0);
  const [isMocking, setIsMocking] = useState(false);

  useEffect(() => {
    if (status === "idle") {
      setMessage(statusMessages.idle);
    } else if (status === "uploading") {
      setMessage(isMocking ? "Loading sample PDFs…" : statusMessages.uploading);
    } else if (status === "processing") {
      setMessage(statusMessages.processing);
    }
  }, [status, isMocking]);

  useEffect(() => {
    return () => {
      if (resultUrl) {
        URL.revokeObjectURL(resultUrl);
      }
    };
  }, [resultUrl]);

  const canCompare = useMemo(() => Boolean(oldFile && newFile && status !== "uploading" && status !== "processing"), [oldFile, newFile, status]);

  const resetProgress = () => {
    setProgress(0);
  };

  const handleFileChange = (event: React.ChangeEvent<HTMLInputElement>, target: "old" | "new") => {
    if (!event.target.files?.length) {
      return;
    }

    const file = event.target.files[0];
    if (target === "old") {
      setOldFile(file);
    } else {
      setNewFile(file);
    }
    setResultUrl(null);
    setResultBlob(null);
    setStatus("idle");
    resetProgress();
  };

  const handleCompare = async () => {
    if (!oldFile || !newFile) {
      return;
    }

    setStatus("uploading");
    setProgress(10);

    const formData = new FormData();
    formData.append("old", oldFile, oldFile.name);
    formData.append("new", newFile, newFile.name);

    try {
      const response = await fetch(`${API_BASE}/api/compare`, {
        method: "POST",
        body: formData
      });

      if (!response.ok) {
        throw new Error(`Request failed with status ${response.status}`);
      }

      setStatus("processing");
      setProgress(60);

      const contentType = response.headers.get("Content-Type") ?? "";
      let pdfBlob: Blob;

      if (contentType.includes("application/json")) {
        const payload = await response.json();
        if (payload?.result) {
          const byteCharacters = atob(payload.result);
          const byteNumbers = new Array(byteCharacters.length);
          for (let i = 0; i < byteCharacters.length; i += 1) {
            byteNumbers[i] = byteCharacters.charCodeAt(i);
          }
          const byteArray = new Uint8Array(byteNumbers);
          pdfBlob = new Blob([byteArray], { type: "application/pdf" });
        } else {
          throw new Error("Unexpected response payload.");
        }
      } else {
        pdfBlob = await response.blob();
      }

      if (resultUrl) {
        URL.revokeObjectURL(resultUrl);
      }

      const objectUrl = URL.createObjectURL(pdfBlob);
      setResultUrl(objectUrl);
      setResultBlob(pdfBlob);
      setPreviewMode("overlay");
      setStatus("complete");
      setProgress(100);
      setMessage("Comparison complete. Use the preview or download the annotated PDF.");
    } catch (error) {
      console.error(error);
      setStatus("error");
      setMessage(
        error instanceof Error ? error.message : "Unable to perform comparison. Please try again."
      );
      resetProgress();
    }
  };

  const handleDownload = () => {
    if (!resultBlob) {
      return;
    }

    const downloadUrl = URL.createObjectURL(resultBlob);
    const anchor = document.createElement("a");
    anchor.href = downloadUrl;
    anchor.download = "compareset-result.pdf";
    anchor.click();
    URL.revokeObjectURL(downloadUrl);
  };

  const handleMockComparison = async () => {
    setIsMocking(true);
    try {
      setStatus("uploading");
      setProgress(20);

      const [oldResponse, newResponse, resultResponse] = await Promise.all([
        fetch("/samples/sample-old.pdf"),
        fetch("/samples/sample-new.pdf"),
        fetch("/samples/sample-result.pdf")
      ]);

      if (!oldResponse.ok || !newResponse.ok || !resultResponse.ok) {
        throw new Error("Sample PDFs not found.");
      }

      const [oldBuffer, newBuffer, resultBlobValue] = await Promise.all([
        oldResponse.arrayBuffer(),
        newResponse.arrayBuffer(),
        resultResponse.blob()
      ]);

      const mockOld = new File([oldBuffer], "sample-old.pdf", { type: "application/pdf" });
      const mockNew = new File([newBuffer], "sample-new.pdf", { type: "application/pdf" });

      setOldFile(mockOld);
      setNewFile(mockNew);

      if (resultUrl) {
        URL.revokeObjectURL(resultUrl);
      }

      const objectUrl = URL.createObjectURL(resultBlobValue);
      setResultBlob(resultBlobValue);
      setResultUrl(objectUrl);

      setPreviewMode("overlay");
      setStatus("complete");
      setProgress(100);
      setMessage("Mock comparison loaded. Download or review the overlay preview.");
    } catch (error) {
      console.error(error);
      setStatus("error");
      setMessage(
        error instanceof Error
          ? error.message
          : "Unable to load mock comparison. Ensure sample PDFs are available."
      );
      resetProgress();
    } finally {
      setIsMocking(false);
    }
  };

  return (
    <div className="viewer-shell">
      <header className="viewer-header">
        <div>
          <h1>CompareSet</h1>
          <p className="subtitle">Hybrid PDF comparison with raster detection and vector overlays.</p>
        </div>
        <div className="header-actions">
          <button
            type="button"
            className="secondary-button"
            onClick={handleMockComparison}
            disabled={status === "uploading" || status === "processing" || isMocking}
            title="Load sample PDFs to validate the interface"
          >
            {isMocking ? "Loading samples…" : "Run Mock Comparison"}
          </button>
          <ThemeToggle theme={theme} onToggle={onToggleTheme} />
        </div>
      </header>

      <section className="controls">
        <div className="file-inputs">
          <label className="file-card">
            <span className="label">Old revision</span>
            <input
              type="file"
              accept="application/pdf"
              onChange={(event) => handleFileChange(event, "old")}
            />
            <span className="filename">{oldFile ? oldFile.name : "Choose a PDF"}</span>
          </label>
          <label className="file-card">
            <span className="label">New revision</span>
            <input
              type="file"
              accept="application/pdf"
              onChange={(event) => handleFileChange(event, "new")}
            />
            <span className="filename">{newFile ? newFile.name : "Choose a PDF"}</span>
          </label>
        </div>
        <div className="primary-actions">
          <div className="mode-toggle" role="group" aria-label="Preview mode">
            <button
              type="button"
              className={previewMode === "side-by-side" ? "active" : ""}
              onClick={() => setPreviewMode("side-by-side")}
            >
              Side-by-side
            </button>
            <button
              type="button"
              className={previewMode === "overlay" ? "active" : ""}
              onClick={() => setPreviewMode("overlay")}
            >
              Overlay
            </button>
          </div>
          <button
            type="button"
            className="primary-button"
            onClick={handleCompare}
            disabled={!canCompare}
          >
            {status === "uploading" || status === "processing" ? "Processing…" : "Compare"}
          </button>
          <button type="button" className="secondary-button" onClick={handleDownload} disabled={!resultBlob}>
            Download result
          </button>
        </div>
      </section>

      <section className="status-panel" aria-live="polite">
        <div className={`status-indicator status-${status}`}>
          <span className="status-dot" />
          <span>{message}</span>
        </div>
        {(status === "uploading" || status === "processing") && (
          <div className="progress-bar">
            <div className="progress" style={{ width: `${progress}%` }} />
          </div>
        )}
      </section>

      <section className={`preview ${previewMode}`}>
        {previewMode === "side-by-side" ? (
          <div className="columns">
            <PdfPreview file={oldFile} label="Old revision" />
            <PdfPreview file={newFile} label="New revision" />
          </div>
        ) : (
          <div className="overlay-preview">
            {resultUrl ? (
              <iframe title="Comparison result" src={resultUrl} />
            ) : (
              <div className="empty-state">Run a comparison to see the annotated PDF.</div>
            )}
          </div>
        )}
      </section>
    </div>
  );
};

export default CompareSetViewer;
