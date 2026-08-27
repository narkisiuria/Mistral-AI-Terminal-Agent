        else:
            confirmation = input(f"procced running: '{shell}' (n/y)> ")
            shell += "\nif ($?) {'success'} else {'FALIURECHECK'}\n"

            if confirmation == "y" or confirmation == "":
                proc.stdin.write(shell)
                proc.stdin.flush()
                time.sleep(0.5)
                result = read_until_prompt(proc)
                
                if "FALIURECHECK" in result:
                    failure_response = call_mistral(system_prompt, f"failed command: {shell}\nreason: {result}")
                    print(failure_response)
                    
                else:
                    cmd, output, prompt = parse_result(result)

                    print(output.strip())
                    session_history.append({"request": client_request, "command": shell.strip(), "output": output.strip()})