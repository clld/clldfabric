/*
 *  Copyright (c) 2006-2009, FlexiGuided GmbH, Berlin, Germany
 *  Author: Jan Behrens <jan.behrens@flexiguided.de>
 *  All rights reserved.
 *
 *  Redistribution and use in source and binary forms, with or without
 *  modification, are permitted provided that the following conditions are
 *  met:
 *
 *  1. Redistributions of source code must retain the above copyright
 *     notice, this list of conditions and the following disclaimer.
 *  2. Redistributions in binary form must reproduce the above copyright
 *     notice, this list of conditions and the following disclaimer in the
 *     documentation and/or other materials provided with the distribution.
 *  3. Neither the name of the FlexiGuided GmbH nor the names of its
 *     contributors may be used to endorse or promote products derived from
 *     this software without specific prior written permission.
 *
 *  THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
 *  "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
 *  LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A
 *  PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER
 *  OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL,
 *  EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO,
 *  PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR
 *  PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF
 *  LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING
 *  NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
 *  SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
 *
 */


#include <postgres.h>
#include <utils/elog.h>
#include <utils/builtins.h>
#include <fmgr.h>
#include <string.h>
#include <unicode/ucnv.h>
#include <unicode/ucol.h>

#ifdef PG_MODULE_MAGIC
PG_MODULE_MAGIC;
#endif


static void pgsqlext_collkey_icu_error(UErrorCode uerror) {
  int sqlerrcode;
  switch (uerror) {
    case U_MEMORY_ALLOCATION_ERROR:
    sqlerrcode = ERRCODE_OUT_OF_MEMORY; break;
    case U_INVALID_CHAR_FOUND:
    case U_TRUNCATED_CHAR_FOUND:
    case U_ILLEGAL_CHAR_FOUND:
    sqlerrcode = ERRCODE_DATA_EXCEPTION; break;
    default:
    sqlerrcode = ERRCODE_INTERNAL_ERROR;
  }
  ereport(ERROR, (sqlerrcode,
    errmsg("libicu error: %s", u_errorName(uerror))
  ));
}

static void pgsqlext_collkey_nomem() {
  ereport(ERROR, (ERRCODE_OUT_OF_MEMORY,
    errmsg("%s", "Memory allocation for collation key generation failed.")
  ));
}

static void pgsqlext_collkey_overflow() {
  ereport(ERROR, (ERRCODE_PROGRAM_LIMIT_EXCEEDED,
    errmsg("%s", "Text is too long for collation key generation.")
  ));
}


PG_FUNCTION_INFO_V1(pgsqlext_collkey);
// this function is NOT thread safe

Datum pgsqlext_collkey(PG_FUNCTION_ARGS) {
  UChar *ustr;
  int32_t ustr_length;
  bytea *output;
  UErrorCode uerror = U_ZERO_ERROR;

  {
    static UConverter *cnv = NULL;
    text *input_string;

    if (!cnv) {
      cnv = ucnv_open("UTF-8", &uerror);
      if (!cnv) pgsqlext_collkey_icu_error(uerror);
    }

    input_string = PG_GETARG_TEXT_P(0);

    ustr_length = ucnv_toUChars(cnv, NULL, 0,
      VARDATA(input_string), VARSIZE(input_string)-VARHDRSZ, &uerror);
    if (uerror != U_BUFFER_OVERFLOW_ERROR && U_FAILURE(uerror))
      pgsqlext_collkey_icu_error(uerror);
    uerror = U_ZERO_ERROR;
    if (ustr_length > SIZE_MAX/sizeof(UChar)) pgsqlext_collkey_overflow();
    ustr = palloc(ustr_length * sizeof(UChar));
    ustr_length = ucnv_toUChars(cnv, ustr, ustr_length,
      VARDATA(input_string), VARSIZE(input_string)-VARHDRSZ, &uerror);
    if (U_FAILURE(uerror)) pgsqlext_collkey_icu_error(uerror);

    PG_FREE_IF_COPY(input_string, 0);
  }

  // ustr is allocated here

  {
    static UCollator *coll = NULL;
    int32_t output_length;

    {
      static char *saved_locale = NULL;
      char *locale;
      locale = DatumGetCString(
        DirectFunctionCall1(textout, PG_GETARG_DATUM(1))
      );
      if (coll && strcmp(locale, saved_locale)) {
        ucol_close(coll);
        coll = NULL;
      }
      if (!coll) {
        free(saved_locale);
        saved_locale = strdup(locale);
        if (!saved_locale) pgsqlext_collkey_nomem();
        coll = ucol_open(saved_locale, &uerror);
        if (!coll) pgsqlext_collkey_icu_error(uerror);
        ucol_setAttribute(coll, UCOL_NORMALIZATION_MODE, UCOL_ON, &uerror);
        // error check below
      }
      pfree(locale);
    }

    {
      bool shifted;
      shifted = PG_GETARG_BOOL(2);
      ucol_setAttribute(coll, UCOL_ALTERNATE_HANDLING,
        shifted ? UCOL_SHIFTED : UCOL_NON_IGNORABLE, &uerror);
      // error check below
    }

    {
      int32_t strength;
      strength = PG_GETARG_INT32(3);
      switch (strength) {
        case 0: ucol_setAttribute(coll, UCOL_STRENGTH, UCOL_DEFAULT,
          &uerror); break;
        case 1: ucol_setAttribute(coll, UCOL_STRENGTH, UCOL_PRIMARY,
          &uerror); break;
        case 2: ucol_setAttribute(coll, UCOL_STRENGTH, UCOL_SECONDARY,
          &uerror); break;
        case 3: ucol_setAttribute(coll, UCOL_STRENGTH, UCOL_TERTIARY,
          &uerror); break;
        case 4: ucol_setAttribute(coll, UCOL_STRENGTH, UCOL_QUATERNARY,
          &uerror); break;
        case 5: ucol_setAttribute(coll, UCOL_STRENGTH, UCOL_IDENTICAL,
          &uerror); break;
        default:
        ereport(ERROR, (ERRCODE_INVALID_PARAMETER_VALUE,
          errmsg("%s", "Illegal collation strength argument.")
        ));
      }
      // error check below
    }

    {
      bool numeric;
      numeric = PG_GETARG_BOOL(4);
      ucol_setAttribute(coll, UCOL_NUMERIC_COLLATION,
        numeric ? UCOL_ON : UCOL_OFF, &uerror);
      // error check below
    }

    // error check:
    if (U_FAILURE(uerror)) pgsqlext_collkey_icu_error(uerror);

    output_length = ucol_getSortKey(coll, ustr, ustr_length, NULL, 0);
    // we create a larger buffer than needed, due to a bug in the ICU library
    if (output_length > SIZE_MAX-VARHDRSZ-4+1) pgsqlext_collkey_overflow();
    output = palloc(output_length + VARHDRSZ - 1 + 4);
    ucol_getSortKey(coll, ustr, ustr_length,
      VARDATA(output), output_length - 1 + 4);
    SET_VARSIZE(output, output_length + VARHDRSZ - 1);

  }

  pfree(ustr);
  PG_RETURN_BYTEA_P(output);
}


