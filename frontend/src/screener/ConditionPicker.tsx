import { useEffect, useRef, useState } from 'react';

import type { ScreenerCondition } from '../api/types';
import { Icon } from '../components/Icon';

/** Props for ConditionPicker. */
interface ConditionPickerProps {
  catalogue: ScreenerCondition[];
  chosen: string[];
  onChange: (chosen: string[]) => void;
}

/**
 * The screen's conditions as editable chips, and a menu to add more.
 * @param props The catalogue, the chosen requests such as "rsi:0:30", and what a change does.
 * @returns The picker.
 */
export function ConditionPicker(props: ConditionPickerProps) {
  const { catalogue, chosen, onChange } = props;
  const [menuOpen, setMenuOpen] = useState(false);
  const [editing, setEditing] = useState<number | null>(null);
  const pickerReference = useRef<HTMLDivElement>(null);
  const byKey = new Map<string, ScreenerCondition>();
  for (const condition of catalogue) {
    byKey.set(condition.key, condition);
  }

  useEffect(() => {
    if (!menuOpen && editing === null) {
      return undefined;
    }
    const close = () => {
      setMenuOpen(false);
      setEditing(null);
    };
    const handlePointerDown = (event: PointerEvent) => {
      if (pickerReference.current !== null && !pickerReference.current.contains(event.target as Node)) {
        close();
      }
    };
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        close();
      }
    };
    document.addEventListener('pointerdown', handlePointerDown);
    document.addEventListener('keydown', handleKeyDown);
    return () => {
      document.removeEventListener('pointerdown', handlePointerDown);
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, [menuOpen, editing]);

  const add = (condition: ScreenerCondition) => {
    const values: string[] = [condition.key];
    for (const parameter of condition.parameters) {
      values.push(String(parameter.default));
    }
    onChange([...chosen, values.join(':')]);
    setMenuOpen(false);
    setEditing(chosen.length);
  };

  const remove = (position: number) => {
    const next = [...chosen];
    next.splice(position, 1);
    onChange(next);
    setEditing(null);
  };

  const update = (position: number, parameterIndex: number, value: string) => {
    const pieces = chosen[position].split(':');
    pieces[parameterIndex + 1] = value;
    const next = [...chosen];
    next[position] = pieces.join(':');
    onChange(next);
  };

  return (
    <div className="indicator-picker" ref={pickerReference}>
      {chosen.map((request, position) => {
        const pieces = request.split(':');
        const condition = byKey.get(pieces[0]);
        const values = pieces.slice(1);
        return (
          <div key={`${request}-${position}`} className="indicator-chip">
            <button type="button" className="indicator-chip-name" onClick={() => setEditing(editing === position ? null : position)} title={condition?.description ?? request}>
              {condition?.label ?? pieces[0]}
              {values.length > 0 ? <span className="mono muted"> {values.join(', ')}</span> : null}
            </button>
            <button type="button" className="indicator-chip-remove" onClick={() => remove(position)} aria-label={`Remove ${request}`}>
              <Icon name="close" size={12} />
            </button>
            {editing === position && condition !== undefined && condition.parameters.length > 0 ? (
              <div className="indicator-editor card">
                <strong>{condition.label}</strong>
                <p className="muted">{condition.description}</p>
                {condition.parameters.map((parameter, parameterIndex) => (
                  <label key={parameter.name}>
                    {parameter.label}
                    <input
                      className="input"
                      type="number"
                      step={parameter.whole_number ? 1 : 0.1}
                      min={parameter.minimum}
                      max={parameter.maximum}
                      defaultValue={values[parameterIndex] ?? parameter.default}
                      onBlur={(event) => update(position, parameterIndex, event.target.value)}
                      onKeyDown={(event) => {
                        if (event.key === 'Enter') {
                          update(position, parameterIndex, event.currentTarget.value);
                        }
                      }}
                    />
                  </label>
                ))}
              </div>
            ) : null}
          </div>
        );
      })}
      <div className="indicator-add">
        <button type="button" className="button" onClick={() => setMenuOpen(!menuOpen)} aria-expanded={menuOpen}>
          + Condition
        </button>
        {menuOpen ? (
          <div className="indicator-menu card condition-menu">
            {catalogue.map((condition) => (
              <button key={condition.key} type="button" className="indicator-option condition-option" onClick={() => add(condition)}>
                <span>{condition.label}</span>
                <span className="muted">{condition.description}</span>
              </button>
            ))}
          </div>
        ) : null}
      </div>
    </div>
  );
}
