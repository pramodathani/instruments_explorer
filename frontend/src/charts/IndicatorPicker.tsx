import { useEffect, useRef, useState } from 'react';

import type { IndicatorDescription } from '../api/types';
import { Icon } from '../components/Icon';

/** Props for IndicatorPicker. */
interface IndicatorPickerProps {
  catalogue: IndicatorDescription[];
  chosen: string[];
  hasVolume: boolean;
  onChange: (chosen: string[]) => void;
}

/**
 * The chosen indicators as editable chips, and a menu to add more, grouped by family.
 * @param props The catalogue, the chosen requests such as "rsi:14", whether volume exists, and what a change does.
 * @returns The picker.
 */
export function IndicatorPicker(props: IndicatorPickerProps) {
  const { catalogue, chosen, hasVolume, onChange } = props;
  const [menuOpen, setMenuOpen] = useState(false);
  const [editing, setEditing] = useState<number | null>(null);
  const pickerReference = useRef<HTMLDivElement>(null);

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
  const byKey = new Map<string, IndicatorDescription>();
  const families: string[] = [];
  for (const description of catalogue) {
    byKey.set(description.key, description);
    if (!families.includes(description.family)) {
      families.push(description.family);
    }
  }

  const add = (description: IndicatorDescription) => {
    const values: string[] = [description.key];
    for (const parameter of description.parameters) {
      values.push(String(parameter.default));
    }
    onChange([...chosen, values.join(':')]);
    setMenuOpen(false);
  };

  const remove = (position: number) => {
    const next = [...chosen];
    next.splice(position, 1);
    onChange(next);
    setEditing(null);
  };

  const updateParameter = (position: number, parameterIndex: number, value: string) => {
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
        const description = byKey.get(pieces[0]);
        const values = pieces.slice(1);
        return (
          <div key={`${request}-${position}`} className="indicator-chip">
            <button
              type="button"
              className="indicator-chip-name"
              onClick={() => setEditing(editing === position ? null : position)}
              title={description?.description ?? request}
            >
              {description?.short_label ?? pieces[0]}
              {values.length > 0 ? <span className="mono muted"> {values.join(', ')}</span> : null}
            </button>
            <button type="button" className="indicator-chip-remove" onClick={() => remove(position)} aria-label={`Remove ${request}`}>
              <Icon name="close" size={12} />
            </button>
            {editing === position && description !== undefined && description.parameters.length > 0 ? (
              <div className="indicator-editor card">
                <strong>{description.label}</strong>
                <p className="muted">{description.description}</p>
                {description.parameters.map((parameter, parameterIndex) => (
                  <label key={parameter.name}>
                    {parameter.label}
                    <input
                      className="input"
                      type="number"
                      step={parameter.whole_number ? 1 : 0.01}
                      min={parameter.minimum}
                      max={parameter.maximum}
                      defaultValue={values[parameterIndex] ?? parameter.default}
                      onBlur={(event) => updateParameter(position, parameterIndex, event.target.value)}
                      onKeyDown={(event) => {
                        if (event.key === 'Enter') {
                          updateParameter(position, parameterIndex, event.currentTarget.value);
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
          + Indicator
        </button>
        {menuOpen ? (
          <div className="indicator-menu card">
            {families.map((family) => (
              <div key={family} className="indicator-family">
                <div className="stat-label">{family}</div>
                {catalogue
                  .filter((description) => description.family === family)
                  .map((description) => {
                    const unavailable = description.needs_volume && !hasVolume;
                    return (
                      <button
                        key={description.key}
                        type="button"
                        className="indicator-option"
                        disabled={unavailable}
                        title={unavailable ? 'Needs volume, which this instrument does not have.' : description.description}
                        onClick={() => add(description)}
                      >
                        <span>{description.label}</span>
                        <span className="muted">{description.placement === 'price' ? 'on price' : description.placement === 'panel' ? 'own pane' : 'flags'}</span>
                      </button>
                    );
                  })}
              </div>
            ))}
          </div>
        ) : null}
      </div>
    </div>
  );
}
