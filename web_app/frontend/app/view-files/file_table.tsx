import React from "react";
import { FileItem } from "./page";

export interface file_table_props {
  files: FileItem[];
  selected: number[];
  setSelected: React.Dispatch<React.SetStateAction<number[]>>;
  downloadFile: (f: FileItem) => (e: React.MouseEvent) => void;
}

const FileTable: React.FC<file_table_props> = ({ files, selected, setSelected, downloadFile }) => {
  const allSelected = files.length > 0 && selected.length === files.length;
  const someSelected = selected.length > 0 && selected.length < files.length;

  const handleSelectAll = () => {
    if (allSelected) {
      // Deselect all
      setSelected([]);
    } else {
      // Select all
      setSelected(files.map(f => f.id));
    }
  };

  return (
    <table className="w-full border mb-4 text-sm">
      <thead>
        <tr className="bg-gray-100 dark:bg-gray-800">
          <th className="border px-2 py-1 bg-white text-black">
            <input
              type="checkbox"
              checked={allSelected}
              ref={(input) => {
                if (input) input.indeterminate = someSelected;
              }}
              onChange={handleSelectAll}
              title="Select/Deselect all files"
            />
          </th>
          <th className="border px-2 py-1 bg-white text-black">ID</th>
          <th className="border px-2 py-1 bg-white text-black">Database</th>
          <th className="border px-2 py-1 bg-white text-black">Download</th>
        </tr>
      </thead>
    <tbody>
      {files.map(f => (
        <tr key={f.id}>
          <td className="border px-2 py-1 text-center">
            <input
              type="checkbox"
              checked={selected.includes(f.id)}
              onChange={e => {
                setSelected(sel => e.target.checked ? [...sel, f.id] : sel.filter(x => x !== f.id));
              }}
              title={`Select file ${f.database}`}
            />
          </td>
          <td className="border px-2 py-1 font-mono">{f.id}</td>
          <td className="border px-2 py-1 font-mono">{f.database}</td>
          <td className="border px-2 py-1 text-center">
            <button
              className="px-2 py-1 rounded bg-blue-600 text-white hover:bg-blue-700 cursor-pointer"
              onClick={downloadFile(f)}
            >Download</button>
          </td>
        </tr>
      ))}
    </tbody>
  </table>
  );
};

export default FileTable;
