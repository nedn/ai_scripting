"""
Refactors Java test classes found within a target directory using AI.

This script automates the process of refactoring Java test classes based on a
user-provided prompt. It follows a similar structure to the rise_snprintf.py example:
1. Uses search_utils to find relevant Java test files (e.g., containing @Test).
2. Uses ai_edit to generate and apply edits to the entire content of the identified files.
3. Includes argument parsing for specifying the target directory and limiting files.
4. Contains comments and documentation to explain the process.

To use this script:
1. Ensure you have the ai_scripting library and its dependencies installed.
2. Ensure 'rg' (ripgrep) is installed and accessible in your PATH.
3. Create an example file (e.g., java-test-refactor.example) showcasing the
   desired "before" and "after" state of a typical refactoring.
4. Run the script, providing the path to your Java project and potentially
   adjusting the prompt within the script for your specific refactoring goal.

Example command:
python /Users/nednguyen/projects/ai_scripting/samples/refactor_java_t.py --target-dir /path/to/your/java/project --max-files 10
"""

import argparse
import os
import shlex
import sys

from rich import console

# --- Path Setup ---
# Assumes the script is in ai_scripting/samples/
# Adjust if your directory structure is different.
SCRIPT_DIR = os.path.abspath(os.path.dirname(__file__))
AI_SCRIPTING_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, ".."))

# Add ai_scripting directory to Python path
if AI_SCRIPTING_DIR not in sys.path:
    sys.path.append(AI_SCRIPTING_DIR)

try:
    from ai_scripting import search_utils
    from ai_scripting import ai_edit
    from ai_scripting import llm_utils
except ImportError as e:
    print(f"Error importing ai_scripting modules: {e}")
    print(f"Ensure the ai_scripting directory ({AI_SCRIPTING_DIR}) is in your PYTHONPATH or accessible.")
    sys.exit(1)

# --- Rich Console ---
console = console.Console()

# --- Constants ---
# Define the name for the example file used to guide the AI.
# This file should contain pairs of "before" and "after" code snippets
# demonstrating the desired refactoring pattern for a Java test class.
# Example structure for java-test-refactor.example:
# ```java
# // Before: Old test class structure
# public class OldTest {
#     @Test
#     public void testSomethingOld() {
#         // ... old assertions ...
#     }
# }
# ```
# ```java
# // After: New refactored test class structure
# public class NewTest {
#     @Test
#     public void testSomethingNew() {
#         // ... new assertions using a different framework/style ...
#     }
# }
# ```
EXAMPLE_FILE_NAME = "java-test-refactor.example"
EXAMPLE_FILE_PATH = os.path.join(SCRIPT_DIR, EXAMPLE_FILE_NAME)

def main():
    """
    Main function to parse arguments, find Java test files,
    generate refactoring edits using AI, and apply them.
    """
    # --- Argument Parsing ---
    parser = argparse.ArgumentParser(
        description='Refactor Java test classes using AI.',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        '--target-dir', "-d",
        required=True,
        help='The root directory of the Java project to scan for test classes.'
    )
    parser.add_argument(
        '--max-files', "-m",
        type=int,
        default=5,
        help='Maximum number of files to apply AI edits to. Set to 0 to apply to all found files.'
    )
    # Consider adding an argument for the prompt if more flexibility is needed:
    # parser.add_argument('--prompt', default="Refactor this Java test class to the new standard.", help='The prompt describing the refactoring task.')

    args = parser.parse_args()

    # --- Validate Target Directory ---
    target_dir = os.path.abspath(os.path.normpath(args.target_dir))
    if not os.path.isdir(target_dir):
        console.print(f"[bold red]Error: Target directory not found or is not a directory:[/bold red] {target_dir}")
        sys.exit(1)

    console.print(f"Target directory set to: {target_dir}")

    # --- Define the AI Refactoring Prompt ---
    # IMPORTANT: Customize this prompt based on the specific refactoring needed.
    # Be clear about the desired changes (e.g., migrate to JUnit 5, use AssertJ assertions,
    # adopt a new base class, implement a specific pattern).
    refactoring_prompt = (
        "Refactor the following Java test class. Update it to use the latest company testing standards, "
        "which include [Specify Standards Here, e.g., JUnit 5, Mockito 5, AssertJ assertions, specific base classes]. "
        "Ensure all imports are updated, deprecated methods are replaced, and the overall structure aligns "
        "with the provided examples. Maintain existing test logic and coverage unless modification is inherent "
        "to the standard update."
    )
    console.print(f"[cyan]Using refactoring prompt:[/cyan] {refactoring_prompt}")

    # --- 1. Search for Java Test Files ---
    # We'll search for files containing the "ChromeTabbedActivityTestRule" instation
    search_regex = shlex.quote(r"new ChromeTabbedActivityTestRule")
    console.print(f"Searching for Java files containing {search_regex} in {target_dir}...")

    try:
        search_results = search_utils.search(
            search_regex=search_regex,
            directory=target_dir,
            file_types=[search_utils.FileTypes.JAVA],
            context_lines=0 # We need the whole file content for whole-file edits
        )
        search_results.print_results()

        if not search_results.matched_files:
            console.print("[yellow]No Java files containing '@Test' were found. Exiting.[/yellow]")
            sys.exit(0)

    except Exception as e:
        console.print_exception()
        console.print(f"[bold red]An error occurred during the search phase: {e}[/bold red]")
        sys.exit(1)

    # --- Limit Files if Necessary ---
    files_to_edit = search_results.matched_files
    if args.max_files > 0 and len(files_to_edit) > args.max_files:
        console.print(f"[yellow]Limiting AI edits to the first {args.max_files} files found. "
                      f"Set --max-files to 0 to apply to all {len(files_to_edit)} files.[/yellow]")
        files_to_edit = files_to_edit[:args.max_files]
    elif args.max_files == 0:
         console.print(f"[green]Processing all {len(files_to_edit)} found files.[/green]")


    # --- 2. Generate an Edit Plan ---
    # Load examples to guide the AI.
    example_content = ai_edit.load_example_file(os.path.join(SCRIPT_DIR, "transit_refactoring.example"))

    console.print("Generating AI edit plan...")
    try:
        # Since we want to refactor the entire test class, we use the
        # REPLACE_WHOLE_FILE strategy. This tells ai_edit to provide the
        # entire file content to the LLM and expect the entire refactored
        # file content back.
        edit_plan = ai_edit.create_ai_plan_for_editing_files(
                files_to_edit,
                prompt=CODE_TRANSIT_REFACTORING_PROMPT,
                examples=example_content,
                model=llm_utils.GeminiModel.GEMINI_2_5_PRO, # Or choose another suitable model
                edit_strategy=ai_edit.EditStrategy.REPLACE_WHOLE_FILE # Edit entire file
        )
    except Exception as e:
        console.print_exception()
        console.print(f"[bold red]An error occurred during AI edit plan creation: {e}[/bold red]")
        sys.exit(1)


    # --- 3. Print the Edit Plan ---
    # This shows which files are targeted for modification.
    edit_plan.print_plan()

    # --- Optional: Review Step ---
    # You might want to add a confirmation step here before applying edits,
    # especially when refactoring many files.
    # E.g., input("Press Enter to apply the edits or Ctrl+C to cancel...")

    # --- 4. Apply the Edits ---
    console.print("Applying AI edits...")
    try:
        # This step modifies the actual files on disk based on the AI's suggestions.
        # Back up your code or use version control before running this!
        edit_plan.apply_edits()
        console.print("[bold green]AI edits applied successfully.[/bold green]")
    except Exception as e:
        console.print_exception()
        console.print(f"[bold red]An error occurred while applying edits: {e}[/bold red]")
        sys.exit(1)

CODE_TRANSIT_REFACTORING_PROMPT = """
Your task is to refactor the tests that use the legacy ChromeTabbedActivityTestRule to use the new FreshCtaTransitTestRule class and its associated methods.

Anywhere you see code like `ChromeTabbedActivityTestRule foo = new ChromeTabbedActivityTestRule()` you would
replace it with `FreshCtaTransitTestRule foo = FreshCtaTransitTestRule mActivityTestRule = ChromeTransitTestRules.freshChromeTabbedActivityRule();`
and update the imports as well as the method calls of `foo` accordingly.

Here is the code definition of FreshCtaTransitTestRule and ChromeTabbedActivityTestRule classes:


[Content of FreshCtaTransitTestRule.java]
```java
package org.chromium.chrome.test.transit;

import android.content.Intent;

import org.junit.rules.TestRule;
import org.junit.runner.Description;
import org.junit.runners.model.Statement;

import org.chromium.base.test.transit.Station;
import org.chromium.build.annotations.NullMarked;
import org.chromium.chrome.browser.ChromeTabbedActivity;
import org.chromium.chrome.test.ChromeTabbedActivityTestRule;
import org.chromium.chrome.test.transit.ntp.RegularNewTabPageStation;
import org.chromium.chrome.test.transit.page.PageStation;
import org.chromium.chrome.test.transit.page.WebPageStation;

/**
 * Rule for integration tests that start a new {@link ChromeTabbedActivity} in each test case.
 *
 * <p>Tests using this can be batched, but the Activity won't be kept between tests; only the
 * process.
 */
@NullMarked
public class FreshCtaTransitTestRule extends BaseCtaTransitTestRule implements TestRule {
    FreshCtaTransitTestRule() {
        super();
    }

    FreshCtaTransitTestRule(ChromeTabbedActivityTestRule testRule) {
        super(testRule);
    }

    @Override
    public Statement apply(Statement statement, Description description) {
        return mActivityTestRule.apply(statement, description);
    }

    /**
     * Start the test in a blank page.
     *
     * @return the active entry {@link PageStation}
     */
    public WebPageStation startOnBlankPage() {
        return ChromeTabbedActivityEntryPoints.startOnBlankPage(mActivityTestRule);
    }

    /**
     * Start the test in a web page served by the test server.
     *
     * @param url the URL of the page to load
     * @return the active entry {@link PageStation}
     */
    public WebPageStation startOnUrl(String url) {
        return ChromeTabbedActivityEntryPoints.startOnUrl(mActivityTestRule, url);
    }

    /**
     * Start the test in a web page served by the test server.
     *
     * @param relativeUrl the relative URL of the page to serve and load
     * @return the active entry {@link PageStation}
     */
    public WebPageStation startOnTestServerUrl(String relativeUrl) {
        assert relativeUrl.startsWith("/") : "|relativeUrl| must be relative";
        String fullUrl = mActivityTestRule.getTestServer().getURL(relativeUrl);
        return ChromeTabbedActivityEntryPoints.startOnUrl(mActivityTestRule, fullUrl);
    }

    /**
     * Start the test in a web page served by the test server.
     *
     * @return the active entry {@link PageStation}
     */
    public RegularNewTabPageStation startFromLauncher() {
        return ChromeTabbedActivityEntryPoints.startFromLauncher(mActivityTestRule);
    }

    /**
     * Start the test by launching Chrome with a given Intent and expecting it to reach the expected
     * Station.
     *
     * @param intent the Intent to launch Chrome with
     * @param expectedStation the state we expect Chrome to reach
     * @return the active entry {@link Station}
     */
    public <T extends Station<?>> T startWithIntent(Intent intent, T expectedStation) {
        return ChromeTabbedActivityEntryPoints.startWithIntent(
                mActivityTestRule, intent, expectedStation);
    }

    /**
     * Start the test by launching Chrome with a given Intent and expecting it to reach the expected
     * Station.
     *
     * @param intent the Intent to launch Chrome with
     * @param expectedStation the state we expect Chrome to reach
     * @return the active entry {@link Station}
     */
    public <T extends Station<?>> T startWithIntentPlusUrl(
            Intent intent, String url, T expectedStation) {
        return ChromeTabbedActivityEntryPoints.startWithIntentPlusUrl(
                mActivityTestRule, intent, url, expectedStation);
    }

    /**
     * Start the test in an NTP.
     *
     * @return the active entry {@link RegularNewTabPageStation}
     */
    public RegularNewTabPageStation startOnNtp() {
        return ChromeTabbedActivityEntryPoints.startOnNtp(mActivityTestRule);
    }

    /**
     * Hop onto Public Transit when the test has already started the ChromeTabbedActivity in a blank
     * page.
     *
     * @return the active entry {@link WebPageStation}
     */
    public WebPageStation alreadyStartedOnBlankPage() {
        return ChromeTabbedActivityEntryPoints.alreadyStartedOnBlankPage();
    }
}
```

[Content of ChromeTabbedActivityTestRule.java]
```java
package org.chromium.chrome.test;

import android.app.ActivityOptions;
import android.app.Instrumentation;
import android.content.Intent;
import android.os.Bundle;
import android.provider.Browser;
import android.text.TextUtils;

import androidx.test.platform.app.InstrumentationRegistry;
import androidx.test.runner.lifecycle.Stage;

import org.junit.Assert;

import org.chromium.base.ActivityState;
import org.chromium.base.ApplicationStatus;
import org.chromium.base.Log;
import org.chromium.base.ThreadUtils;
import org.chromium.base.test.util.ApplicationTestUtils;
import org.chromium.base.test.util.CallbackHelper;
import org.chromium.base.test.util.CriteriaHelper;
import org.chromium.chrome.R;
import org.chromium.chrome.browser.ChromeTabbedActivity;
import org.chromium.chrome.browser.omnibox.UrlBar;
import org.chromium.chrome.browser.password_manager.PasswordManagerTestHelper;
import org.chromium.chrome.browser.tab.Tab;
import org.chromium.chrome.browser.tab.TabCreationState;
import org.chromium.chrome.browser.tab.TabLaunchType;
import org.chromium.chrome.browser.tab.TabSelectionType;
import org.chromium.chrome.browser.tabmodel.TabModel;
import org.chromium.chrome.browser.tabmodel.TabModelObserver;
import org.chromium.chrome.test.util.ChromeTabUtils;
import org.chromium.chrome.test.util.MenuUtils;
import org.chromium.chrome.test.util.NewTabPageTestUtils;
import org.chromium.chrome.test.util.WaitForFocusHelper;

import java.util.concurrent.TimeoutException;

/** Custom ActivityTestRule for tests using ChromeTabbedActivity */
public class ChromeTabbedActivityTestRule extends ChromeActivityTestRule<ChromeTabbedActivity> {
    private static final String TAG = "ChromeTabbedATR";

    public ChromeTabbedActivityTestRule() {
        super(ChromeTabbedActivity.class);
    }

    private Bundle noAnimationLaunchOptions() {
        return ActivityOptions.makeCustomAnimation(getActivity(), 0, 0).toBundle();
    }

    public void resumeMainActivityFromLauncher() throws Exception {
        Assert.assertNotNull(getActivity());
        Assert.assertTrue(
                ApplicationStatus.getStateForActivity(getActivity()) == ActivityState.STOPPED
                        || ApplicationStatus.getStateForActivity(getActivity())
                                == ActivityState.PAUSED);

        Intent launchIntent =
                getActivity()
                        .getPackageManager()
                        .getLaunchIntentForPackage(getActivity().getPackageName());
        launchIntent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
        launchIntent.addFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP);
        getActivity().startActivity(launchIntent, noAnimationLaunchOptions());
        ApplicationTestUtils.waitForActivityState(getActivity(), Stage.RESUMED);
    }

    /** Simulates starting Main Activity from launcher, blocks until it is started. */
    public void startMainActivityFromLauncher() {
        startMainActivityWithURL(null);
    }

    /**
     * Starts the Main activity on the specified URL. Passing a null URL ensures the default page is
     * loaded, which is the NTP with a new profile .
     */
    public void startMainActivityWithURL(String url) {
        // Only launch Chrome.
        Intent intent =
                new Intent(TextUtils.isEmpty(url) ? Intent.ACTION_MAIN : Intent.ACTION_VIEW);
        intent.addCategory(Intent.CATEGORY_LAUNCHER);
        startMainActivityFromIntent(intent, url);
    }

    /**
     * Starts the Main activity and open a blank page.
     * This is faster and less flakiness-prone than starting on the NTP.
     */
    public void startMainActivityOnBlankPage() {
        startMainActivityWithURL("about:blank");
    }

    /**
     * Starts the Main activity as if it was started from an external application, on the
     * specified URL.
     */
    public void startMainActivityFromExternalApp(String url, String appId) {
        Intent intent = new Intent(Intent.ACTION_VIEW);
        if (appId != null) {
            intent.putExtra(Browser.EXTRA_APPLICATION_ID, appId);
        }
        startMainActivityFromIntent(intent, url);
    }

    /**
     * Starts the Main activity using the passed intent, and using the specified URL. This method
     * waits for DEFERRED_STARTUP to fire as well as a subsequent idle-sync of the main looper
     * thread, and the initial tab must either complete its load or it must crash before this method
     * will return.
     */
    public void startMainActivityFromIntent(Intent intent, String url) {
        // Sets up password store. This fakes the Google Play Services password store for
        // integration tests.
        PasswordManagerTestHelper.setUpGmsCoreFakeBackends();
        prepareUrlIntent(intent, url);
        startActivityCompletely(intent);
        if (!getActivity().isInOverviewMode()) {
            waitForFirstFrame();
        }
    }

    @Override
    public void waitForActivityCompletelyLoaded() {
        CriteriaHelper.pollUiThread(
                () -> getActivity().getActivityTab() != null || getActivity().isInOverviewMode(),
                "Tab never selected/initialized and no overview page is showing.");

        if (!getActivity().isInOverviewMode()) {
            super.waitForActivityCompletelyLoaded();
        } else {
            Assert.assertTrue(waitForDeferredStartup());
        }
    }

    /**
     * Open an incognito tab by invoking the 'new incognito' menu item.
     * Returns when receiving the 'PAGE_LOAD_FINISHED' notification.
     */
    public Tab newIncognitoTabFromMenu() {
        final CallbackHelper createdCallback = new CallbackHelper();
        final CallbackHelper selectedCallback = new CallbackHelper();

        TabModel incognitoTabModel = getActivity().getTabModelSelector().getModel(true);
        TabModelObserver observer =
                new TabModelObserver() {
                    @Override
                    public void didAddTab(
                            Tab tab,
                            @TabLaunchType int type,
                            @TabCreationState int creationState,
                            boolean markedForSelection) {
                        createdCallback.notifyCalled();
                    }

                    @Override
                    public void didSelectTab(Tab tab, @TabSelectionType int type, int lastId) {
                        selectedCallback.notifyCalled();
                    }
                };
        ThreadUtils.runOnUiThreadBlocking(() -> incognitoTabModel.addObserver(observer));

        MenuUtils.invokeCustomMenuActionSync(
                InstrumentationRegistry.getInstrumentation(),
                getActivity(),
                R.id.new_incognito_tab_menu_id);

        try {
            createdCallback.waitForCallback(0);
        } catch (TimeoutException ex) {
            throw new AssertionError("Never received tab created event", ex);
        }
        try {
            selectedCallback.waitForCallback(0);
        } catch (TimeoutException ex) {
            throw new AssertionError("Never received tab selected event", ex);
        }
        ThreadUtils.runOnUiThreadBlocking(() -> incognitoTabModel.removeObserver(observer));

        Tab tab = getActivity().getActivityTab();

        ChromeTabUtils.waitForTabPageLoaded(tab, (String) null);
        NewTabPageTestUtils.waitForNtpLoaded(tab);
        InstrumentationRegistry.getInstrumentation().waitForIdleSync();
        Log.d(TAG, "newIncognitoTabFromMenu <<");
        return tab;
    }

    /**
     * New multiple incognito tabs by invoking the 'new incognito' menu item n times.
     * @param n The number of tabs you want to create.
     */
    public void newIncognitoTabsFromMenu(int n) {
        while (n > 0) {
            newIncognitoTabFromMenu();
            --n;
        }
    }

    /**
     * Looks up the Omnibox in the view hierarchy and types the specified text into it, requesting
     * focus and using an inter-character delay of 200ms.
     *
     * @param oneCharAtATime Whether to type text one character at a time or all at once.
     */
    public void typeInOmnibox(String text, boolean oneCharAtATime) throws InterruptedException {
        final UrlBar urlBar = getActivity().findViewById(R.id.url_bar);
        Assert.assertNotNull(urlBar);

        WaitForFocusHelper.acquireFocusForView(urlBar);

        ThreadUtils.runOnUiThreadBlocking(
                () -> {
                    if (!oneCharAtATime) {
                        urlBar.setText(text);
                    }
                });

        if (oneCharAtATime) {
            final Instrumentation instrumentation = InstrumentationRegistry.getInstrumentation();
            for (int i = 0; i < text.length(); ++i) {
                instrumentation.sendStringSync(text.substring(i, i + 1));
                // Let's put some delay between key strokes to simulate a user pressing the keys.
                Thread.sleep(20);
            }
        }
    }
}
```
"""
if __name__ == "__main__":
    main()
