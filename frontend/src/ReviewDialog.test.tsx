import { useState } from "react";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, it } from "vitest";
import { ReviewDialog } from "./ReviewDialog";

afterEach(cleanup);
function Fixture() {
  const [open, setOpen] = useState(false);
  return <><button onClick={() => setOpen(true)}>Review fixture</button>
    {open && <ReviewDialog label="Fixture scope" onCancel={() => setOpen(false)}>
      <p>Fictional scope, not owner data.</p><button onClick={() => setOpen(false)}>Cancel</button>
    </ReviewDialog>}</>;
}
it("focuses the inline scope and restores the initiating control on Escape", () => {
  render(<Fixture />);
  const trigger = screen.getByRole("button", { name: "Review fixture" });
  trigger.focus(); fireEvent.click(trigger);
  const dialog = screen.getByRole("alertdialog", { name: "Fixture scope" });
  expect(dialog).toHaveFocus(); expect(dialog).toHaveAttribute("aria-modal", "false");
  fireEvent.keyDown(dialog, { key: "Escape" });
  expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument(); expect(trigger).toHaveFocus();
});
it("does not close or approve the review just because Enter is pressed on its scope", () => {
  render(<Fixture />); fireEvent.click(screen.getByRole("button", { name: "Review fixture" }));
  const dialog = screen.getByRole("alertdialog", { name: "Fixture scope" });
  fireEvent.keyDown(dialog, { key: "Enter" }); expect(dialog).toBeInTheDocument();
});
