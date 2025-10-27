import { useEffect, useState } from "react";

type PdfPreviewProps = {
  file: File | null;
  label: string;
};

const PdfPreview: React.FC<PdfPreviewProps> = ({ file, label }) => {
  const [source, setSource] = useState<string | null>(null);

  useEffect(() => {
    if (!file) {
      setSource(null);
      return undefined;
    }

    const objectUrl = URL.createObjectURL(file);
    setSource(objectUrl);

    return () => {
      URL.revokeObjectURL(objectUrl);
    };
  }, [file]);

  return (
    <div className="pdf-preview">
      <header>
        <span>{label}</span>
      </header>
      {source ? (
        <iframe title={label} src={source} />
      ) : (
        <div className="empty-state">Upload a PDF to preview.</div>
      )}
    </div>
  );
};

export default PdfPreview;
