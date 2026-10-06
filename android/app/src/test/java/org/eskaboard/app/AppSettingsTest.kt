package org.eskaboard.app

import org.junit.Assert.assertEquals
import org.junit.Test

class AppSettingsTest {
    @Test
    fun pageJsonHasTheLanguageAndHiddenTools() {
        assertEquals("""{"lang":"","hidden":[],"autoPaste":false}""", AppSettings.pageJson("", emptySet()))
        assertEquals(
            """{"lang":"fr","hidden":["esc","paste","files","shots"],"autoPaste":true}""",
            AppSettings.pageJson("fr", setOf("shots", "esc", "files", "paste"), true), // in toolbar order
        )
    }

    @Test
    fun unknownValuesNeverReachThePage() {
        assertEquals(
            """{"lang":"","hidden":["copy"],"autoPaste":false}""",
            AppSettings.pageJson("x\"});alert(1)//", setOf("copy", "\"]}", "unknown")),
        )
    }

    @Test
    fun toolNamesMatchThePage() {
        // data-tool values in phonekb/static/index.html
        assertEquals(listOf("enter", "esc", "erase", "copy", "paste", "files", "shots"), AppSettings.TOOLS)
    }
}
