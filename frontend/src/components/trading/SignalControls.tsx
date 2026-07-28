import { Select } from "antd";
import { SIGNAL_GATES } from "../../shared/constants";
import { displayText, isTruthyFlag } from "../../shared/format";
import type { Setup } from "../../shared/types";

export function GateList({ setup }: { setup?: Setup }) {
  return (
    <div className="gate-list">
      {SIGNAL_GATES.map(([key, label], index) => {
        const pass = setup ? isTruthyFlag(setup[key]) : false;
        return (
          <div className="gate" key={key}>
            <span><i>{index + 1}</i>{label}</span>
            <b className={pass ? "positive" : "warning"}>
              <em className={pass ? "gate-dot pass" : "gate-dot wait"} />
              {pass ? "ĐẠT" : "CHỜ"}
            </b>
          </div>
        );
      })}
    </div>
  );
}

export function SetupPicker({ setups, selected, onSelect }: {
  setups: Setup[];
  selected?: Setup;
  onSelect: (setup: Setup) => void;
}) {
  const value = selected
    ? displayText(selected.symbol) + displayText(selected.side)
    : undefined;

  return (
    <Select
      className="setup-select"
      value={value}
      placeholder="Chọn một thiết lập"
      options={setups.map((setup) => ({
        value: displayText(setup.symbol) + displayText(setup.side),
        label: `${displayText(setup.base)} · ${displayText(setup.side)} · ${displayText(setup.status)}`
      }))}
      onChange={(nextValue) => {
        const setup = setups.find((item) =>
          displayText(item.symbol) + displayText(item.side) === nextValue
        );
        if (setup) onSelect(setup);
      }}
    />
  );
}
