import {render,screen} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import {expect,it,vi} from "vitest";
import {App} from "./App";
it("submits a question and renders grounded sources",async()=>{vi.stubGlobal("fetch",vi.fn().mockResolvedValue({ok:true,json:async()=>({answer:"Start with user goals.",mode:"extractive",sources:[{title:"Example",path:"example.md",excerpt:"Start with user goals.",score:1}]})}));render(<App/>);await userEvent.type(screen.getByLabelText(/ask the example/i),"How do I plan?");await userEvent.click(screen.getByRole("button",{name:"Ask"}));expect(await screen.findByText("Start with user goals.",{selector:".answer > p"})).toBeInTheDocument();expect(screen.getByText("example.md")).toBeInTheDocument();});
