import type { ReactNode } from 'react';

export const inputClass =
  'w-full rounded border border-gray-300 px-3 py-2 text-sm aria-invalid:border-red-600';

export const errorId = (fieldId: string): string => `${fieldId}-error`;

interface FieldProps {
  label: string;
  htmlFor: string;
  error?: string;
  children: ReactNode;
}

/** Label, control and validation message for one form field.
 * The control should point at the message with `aria-describedby={errorId(id)}`.
 */
export default function Field({ label, htmlFor, error, children }: FieldProps) {
  return (
    <div>
      <label htmlFor={htmlFor} className="mb-1 block text-sm font-medium">{label}</label>
      {children}
      {error && <p id={errorId(htmlFor)} className="mt-1 text-sm text-red-600">{error}</p>}
    </div>
  );
}
