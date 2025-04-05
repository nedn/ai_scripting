import unittest
from unittest.mock import patch, MagicMock
from ai_scripting.search_utils import gather_search_results, CodeMatchedResult, CodeBlock, Line


_complex_rg_output = """\
/Users/Test/RISE/extlib/src/Library/Utilities/Communications/SocketCommunications.cpp
42-	if( error == SOCKET_ERROR )
43-	{
44-		if( error == WSAVERNOTSUPPORTED ) {
45:			sprintf( buffer, "WSAStartup error.\\nRequested Winsock v%d.%d, found v%d.%d.",
46-			WINSOCK_MAJOR_VERSION, WINSOCK_MINOR_VERSION,
47-			LOBYTE( d_winsockData.wVersion ), HIBYTE( d_winsockData.wVersion ) );
48-			WSACleanup();
49-		} else {
50:			sprintf( buffer, "WSAStartup error (%d)", WSAGetLastError() );
51-		}
52-
53-		GlobalLog()->PrintSourceError( buffer, __FILE__, __LINE__ );

/Users/Test/RISE/extlib/libpng/pngrutil.c
278-         char umsg[50];
279-
280-         if (ret == Z_BUF_ERROR)
281:            sprintf(umsg,"Buffer error in compressed datastream in %s chunk",
282-                png_ptr->chunk_name);
283-         else if (ret == Z_DATA_ERROR)
284:            sprintf(umsg,"Data error in compressed datastream in %s chunk",
285-                png_ptr->chunk_name);
286-         else
287:            sprintf(umsg,"Incomplete compressed datastream in %s chunk",
288-                png_ptr->chunk_name);
289-         png_warning(png_ptr, umsg);
290-#else
--
317-#if !defined(PNG_NO_STDIO) && !defined(_WIN32_WCE)
318-      char umsg[50];
319-
320:      sprintf(umsg, "Unknown zTXt compression type %d", comp_type);
321-      png_warning(png_ptr, umsg);
322-#else
323-      png_warning(png_ptr, "Unknown zTXt compression type");

/Users/Test/RISE/extlib/libtiff/tif_getimage.c
77-    int colorchannels;
78-
79-    if (!tif->tif_decodestatus) {
80:	sprintf(emsg, "Sorry, requested compression method is not configured");
81-	return (0);
82-    }
83-    switch (td->td_bitspersample) {
--
85-    case 8: case 16:
86-	break;
87-    default:
88:	sprintf(emsg, "Sorry, can not handle images with %d-bit samples",
89-	    td->td_bitspersample);
90-	return (0);
91-    }
--
99-	    photometric = PHOTOMETRIC_RGB;
100-	    break;
101-	default:
102:	    sprintf(emsg, "Missing needed %s tag", photoTag);
103-	    return (0);
104-	}
105-    }
--
110-	if (td->td_planarconfig == PLANARCONFIG_CONTIG
111-            && td->td_samplesperpixel != 1
112-            && td->td_bitspersample < 8 ) {
113:	    sprintf(emsg,
114-                    "Sorry, can not handle contiguous data with %s=%d, "
115-                    "and %s=%d and Bits/Sample=%d",
116-                    photoTag, photometric,
--
126-	break;
127-    case PHOTOMETRIC_YCBCR:
128-	if (td->td_planarconfig != PLANARCONFIG_CONTIG) {
129:	    sprintf(emsg, "Sorry, can not handle YCbCr images with %s=%d",
130-		"Planarconfiguration", td->td_planarconfig);
131-	    return (0);
132-	}
133-	break;
134-    case PHOTOMETRIC_RGB:
135-	if (colorchannels < 3) {
136:	    sprintf(emsg, "Sorry, can not handle RGB image with %s=%d",
137-		"Color channels", colorchannels);
138-	    return (0);
139-	}
--
143-		uint16 inkset;
144-		TIFFGetFieldDefaulted(tif, TIFFTAG_INKSET, &inkset);
145-		if (inkset != INKSET_CMYK) {
146:		    sprintf(emsg,
147-			    "Sorry, can not handle separated image with %s=%d",
148-			    "InkSet", inkset);
149-		    return 0;
150-		}
151-		if (td->td_samplesperpixel < 4) {
152:		    sprintf(emsg,
153-			    "Sorry, can not handle separated image with %s=%d",
154-			    "Samples/pixel", td->td_samplesperpixel);
155-		    return 0;
--
158-	}
159-    case PHOTOMETRIC_LOGL:
160-	if (td->td_compression != COMPRESSION_SGILOG) {
161:	    sprintf(emsg, "Sorry, LogL data must have %s=%d",
162-		"Compression", COMPRESSION_SGILOG);
163-	    return (0);
164-	}
--
166-    case PHOTOMETRIC_LOGLUV:
167-	if (td->td_compression != COMPRESSION_SGILOG &&
168-		td->td_compression != COMPRESSION_SGILOG24) {
169:	    sprintf(emsg, "Sorry, LogLuv data must have %s=%d or %d",
170-		"Compression", COMPRESSION_SGILOG, COMPRESSION_SGILOG24);
171-	    return (0);
172-	}
173-	if (td->td_planarconfig != PLANARCONFIG_CONTIG) {
174:	    sprintf(emsg, "Sorry, can not handle LogLuv images with %s=%d",
175-		"Planarconfiguration", td->td_planarconfig);
176-	    return (0);
177-	}
--
179-    case PHOTOMETRIC_CIELAB:
180-	break;
181-    default:
182:	sprintf(emsg, "Sorry, can not handle image with %s=%d",
183-	    photoTag, photometric);
184-	return (0);
185-    }
--
245-    case 8: case 16:
246-	break;
247-    default:
248:	sprintf(emsg, "Sorry, can not handle images with %d-bit samples",
249-	    img->bitspersample);
250-	return (0);
251-    }
--
295-	    img->photometric = PHOTOMETRIC_RGB;
296-	    break;
297-	default:
298:	    sprintf(emsg, "Missing needed %s tag", photoTag);
299-	    return (0);
300-	}
301-    }
--
303-    case PHOTOMETRIC_PALETTE:
304-	if (!TIFFGetField(tif, TIFFTAG_COLORMAP,
305-	    &red_orig, &green_orig, &blue_orig)) {
306:	    sprintf(emsg, "Missing required \"Colormap\" tag");
307-	    return (0);
308-	}
309-
--
313-        img->greencmap = (uint16 *) _TIFFmalloc(sizeof(uint16)*n_color);
314-        img->bluecmap = (uint16 *) _TIFFmalloc(sizeof(uint16)*n_color);
315-        if( !img->redcmap || !img->greencmap || !img->bluecmap ) {
316:	    sprintf(emsg, "Out of memory for colormap copy");
317-	    return (0);
318-        }
319-


22 matches
22 matched lines
3 files contained matches
2040 files searched
54016 bytes printed
16681608 bytes searched
0.322302 seconds spent searching
0.065929 seconds
"""

class TestGatherSearchResults(unittest.TestCase):
    def setUp(self):
        # Common test data
        self.test_folder = "/test/folder"
        self.basic_rg_args = "-e 'sprintf\s*\(' --line-number --with-filename --context=2 --heading --stats"

        # Sample rg output with matches
        self.simple_rg_output = """\
/path/to/file1.py
10-    def some_function():
11:    print("test")
12-    return True

/path/to/file2.py
5-    def another_function():
6:    print("test2")
7:    print("test3")
8-    return False

3 matches
3 matched lines
2 files contained matches
"""

        # Sample rg output with no matches
        self.no_matches_output = """\
0 matches
0 matched lines
0 files contained matches
2040 files searched
0 bytes printed
16681608 bytes searched
0.302707 seconds spent searching
0.061756 seconds
"""

        # Complex rg output for testing various formats
        self.complex_output = _complex_rg_output

    @patch('ai_scripting.search_utils.run_rg')
    def test_successful_search_with_matches(self, mock_run_rg):
        # Setup mock
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = self.simple_rg_output
        mock_result.stderr = ""
        mock_run_rg.return_value = mock_result

        # Execute
        result = gather_search_results(self.basic_rg_args, self.test_folder)

        # Assertions
        self.assertIsInstance(result, CodeMatchedResult)
        self.assertEqual(result.total_files_matched, 2)
        self.assertEqual(result.total_lines_matched, 3)
        self.assertEqual(len(result.matched_blocks), 2)

        # Check first match
        first_match = result.matched_blocks[0]
        self.assertEqual(first_match.filepath, "/path/to/file1.py")
        self.assertEqual(first_match.start_line, 10)
        self.assertEqual(first_match.end_line, 12)
        self.assertEqual(len(first_match.lines), 3)
        
        # Check second match
        second_match = result.matched_blocks[1]
        self.assertEqual(second_match.filepath, "/path/to/file2.py")
        self.assertEqual(second_match.start_line, 5)
        self.assertEqual(second_match.end_line, 8)
        self.assertEqual(len(second_match.lines), 4)

    @patch('ai_scripting.search_utils.run_rg')
    def test_search_with_no_matches(self, mock_run_rg):
        # Setup mock
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_result.stderr = self.no_matches_output
        mock_run_rg.return_value = mock_result

        # Execute
        result = gather_search_results(self.basic_rg_args, self.test_folder)

        # Assertions
        self.assertIsInstance(result, CodeMatchedResult)
        self.assertEqual(result.total_files_matched, 0)
        self.assertEqual(result.total_lines_matched, 0)
        self.assertEqual(len(result.matched_blocks), 0)

    @patch('ai_scripting.search_utils.run_rg')
    def test_search_with_rg_error(self, mock_run_rg):
        # Setup mock
        mock_result = MagicMock()
        mock_result.returncode = 2
        mock_result.stdout = ""
        mock_result.stderr = "rg command failed"
        mock_run_rg.return_value = mock_result

        # Execute
        result = gather_search_results(self.basic_rg_args, self.test_folder)

        # Assertions
        self.assertIsInstance(result, CodeMatchedResult)
        self.assertEqual(result.total_files_matched, 0)
        self.assertEqual(result.total_lines_matched, 0)
        self.assertEqual(len(result.matched_blocks), 0)

    @patch('ai_scripting.search_utils.run_rg')
    def test_search_with_complex_output(self, mock_run_rg):
        # Setup mock with complex output including various separators and line formats
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = self.complex_output
        mock_result.stderr = ""
        mock_run_rg.return_value = mock_result

        # Execute
        result = gather_search_results(self.basic_rg_args, self.test_folder)

        # Assertions
        self.assertIsInstance(result, CodeMatchedResult)
        self.assertEqual(result.total_files_matched, 3)
        self.assertEqual(result.total_lines_matched, 22)
        self.assertEqual(len(result.matched_blocks), 16)

        # Check first block
        first_block = result.matched_blocks[0]
        self.assertEqual(first_block.filepath, "/Users/Test/RISE/extlib/src/Library/Utilities/Communications/SocketCommunications.cpp")
        self.assertEqual(first_block.start_line, 42)
        self.assertEqual(first_block.end_line, 53)
        self.assertEqual(len(first_block.lines), 12)

        # Check second block
        second_block = result.matched_blocks[1]
        self.assertEqual(second_block.filepath, "/Users/Test/RISE/extlib/libpng/pngrutil.c")
        self.assertEqual(second_block.start_line, 278)
        self.assertEqual(second_block.end_line, 290)
        self.assertEqual(len(second_block.lines), 13)

        # Check third block
        third_block = result.matched_blocks[2]
        self.assertEqual(third_block.filepath, "/Users/Test/RISE/extlib/libpng/pngrutil.c")
        self.assertEqual(third_block.start_line, 317)
        self.assertEqual(third_block.end_line, 323)
        self.assertEqual(len(third_block.lines), 7)

    @patch('ai_scripting.search_utils.run_rg')
    def test_search_with_missing_required_flags(self, mock_run_rg):
        # Test with missing required flags - should raise ValueError
        incomplete_args = "-e 'test'"
        
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = self.simple_rg_output
        mock_result.stderr = ""
        mock_run_rg.return_value = mock_result

        # Execute
        with self.assertRaises(ValueError):
            gather_search_results(incomplete_args, self.test_folder)

if __name__ == '__main__':
    unittest.main()
