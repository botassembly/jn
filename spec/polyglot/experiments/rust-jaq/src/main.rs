use jaq_interpret::{Ctx, FilterT, ParseCtx, RcIter, Val};
use std::io::{self, BufRead, Write};

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let args: Vec<String> = std::env::args().collect();

    if args.len() < 2 {
        eprintln!("Usage: jaq-filter <expression>");
        eprintln!("Reads NDJSON from stdin, applies jq expression, writes to stdout");
        std::process::exit(1);
    }

    let expr = &args[1];

    // Parse the jq expression
    let (filter, errs) = jaq_parse::parse(expr, jaq_parse::main());
    if !errs.is_empty() {
        for err in errs {
            eprintln!("Parse error: {:?}", err);
        }
        std::process::exit(1);
    }
    let filter = filter.unwrap();

    // Build definitions with standard library
    let mut defs = ParseCtx::new(Vec::new());
    defs.insert_natives(jaq_core::core());
    defs.insert_defs(jaq_std::std());

    // Compile the filter
    let filter = defs.compile(filter);
    if !defs.errs.is_empty() {
        eprintln!("Compile error: {} error(s)", defs.errs.len());
        std::process::exit(1);
    }

    // Process NDJSON from stdin
    let stdin = io::stdin();
    let stdout = io::stdout();
    let mut stdout = stdout.lock();

    for line in stdin.lock().lines() {
        let line = line?;
        if line.is_empty() {
            continue;
        }

        let input: serde_json::Value = serde_json::from_str(&line)?;
        let input = Val::from(input);

        let inputs = RcIter::new(std::iter::empty());
        let ctx = Ctx::new([], &inputs);

        for output in filter.run((ctx.clone(), input)) {
            match output {
                Ok(val) => {
                    let json: serde_json::Value = val.into();
                    serde_json::to_writer(&mut stdout, &json)?;
                    writeln!(stdout)?;
                }
                Err(err) => {
                    eprintln!("Error: {:?}", err);
                }
            }
        }
    }

    Ok(())
}
