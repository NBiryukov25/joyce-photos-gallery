#!/usr/bin/env python3
"""
Generates rename_photos.shortcut — an iOS Shortcuts file.

How to use:
  python3 make_rename_shortcut.py

Then transfer rename_photos.shortcut to your iPhone:
  - AirDrop it
  - Put it in iCloud Drive and open it from Files app
  - Email it to yourself

On iPhone: tap the file → "Add Shortcut"

What the shortcut does:
  1. Asks you to type a prefix (e.g. "Joyce")
  2. Asks you to pick a folder
  3. Renames every file in that folder to: Joyce_1.jpg, Joyce_2.jpg, etc.
"""
import plistlib
import uuid

RC = '￼'  # object replacement character — marks variable positions in text tokens


def uid():
    return str(uuid.uuid4()).upper()


def action_ref(action_uuid, output_name=''):
    """Reference the output of a previous action (Shortcuts magic variable)."""
    return {
        'Value': {
            'Type': 'ActionOutput',
            'OutputUUID': action_uuid,
            'OutputName': output_name,
        },
        'WFSerializationType': 'WFTextTokenAttachment',
    }


def text_with_vars(template, attachments):
    """
    Interpolated text value for Shortcuts.
    template:    string using RC as variable placeholders
    attachments: dict of '{offset, length}' -> inner Value dict from action_ref/named_var
    """
    return {
        'Value': {
            'string': template,
            'attachmentsByRange': attachments,
        },
        'WFSerializationType': 'WFTextTokenString',
    }


# ── Action UUIDs ─────────────────────────────────────────────────────────────
ask_uuid      = uid()
folder_uuid   = uid()
contents_uuid = uid()
repeat_uuid   = uid()
group_id      = uid()   # shared between Repeat and End Repeat
text_uuid     = uid()

# ── Actions ──────────────────────────────────────────────────────────────────
actions = [

    # 1. Ask the user for a filename prefix
    {
        'WFWorkflowActionIdentifier': 'is.workflow.actions.ask',
        'WFWorkflowActionParameters': {
            'UUID': ask_uuid,
            'WFAskActionPrompt': 'Enter filename prefix (e.g. Joyce)',
            'WFInputType': 'Text',
            'WFAskActionDefaultAnswer': 'Photo',
            'CustomOutputName': 'Prefix',
        },
    },

    # 2. Prompt the user to pick a folder
    {
        'WFWorkflowActionIdentifier': 'is.workflow.actions.getfile',
        'WFWorkflowActionParameters': {
            'UUID': folder_uuid,
            'WFGetFilesActionSelectFolder': True,
            'SelectingMultipleItems': False,
        },
    },

    # 3. Get all files inside that folder
    {
        'WFWorkflowActionIdentifier': 'is.workflow.actions.getcontentsoffolder',
        'WFWorkflowActionParameters': {
            'UUID': contents_uuid,
            'WFInput': action_ref(folder_uuid, 'File'),
        },
    },

    # 4. Loop over each file (Repeat with Each)
    {
        'WFWorkflowActionIdentifier': 'is.workflow.actions.repeatwith',
        'WFWorkflowActionParameters': {
            'UUID': repeat_uuid,
            'GroupingIdentifier': group_id,
            'WFControlFlowMode': 0,   # 0 = block start
            'WFInput': action_ref(contents_uuid, 'Contents of Folder'),
        },
    },

    # 5. Build the new filename:  Prefix_N
    #    Shortcuts preserves the original file extension automatically.
    {
        'WFWorkflowActionIdentifier': 'is.workflow.actions.gettext',
        'WFWorkflowActionParameters': {
            'UUID': text_uuid,
            'WFTextActionText': text_with_vars(
                RC + '_' + RC,
                {
                    '{0, 1}': action_ref(ask_uuid, 'Prefix')['Value'],
                    '{2, 1}': action_ref(repeat_uuid, 'Repeat Index')['Value'],
                },
            ),
        },
    },

    # 6. Rename the current file
    {
        'WFWorkflowActionIdentifier': 'is.workflow.actions.renamefile',
        'WFWorkflowActionParameters': {
            'UUID': uid(),
            'WFInput':    action_ref(repeat_uuid, 'Repeat Item'),
            'WFFilename': action_ref(text_uuid, 'Text'),
        },
    },

    # 7. End the loop
    {
        'WFWorkflowActionIdentifier': 'is.workflow.actions.endrepeat',
        'WFWorkflowActionParameters': {
            'UUID': uid(),
            'GroupingIdentifier': group_id,
            'WFControlFlowMode': 2,   # 2 = block end
        },
    },

    # 8. Show a confirmation
    {
        'WFWorkflowActionIdentifier': 'is.workflow.actions.showresult',
        'WFWorkflowActionParameters': {
            'UUID': uid(),
            'Text': 'Done! All photos have been renamed.',
        },
    },
]

# ── Shortcut wrapper ──────────────────────────────────────────────────────────
shortcut_data = {
    'WFWorkflowClientVersion': '1249.6',
    'WFWorkflowMinimumClientVersion': 900,
    'WFWorkflowMinimumClientVersionString': '900',
    'WFWorkflowIcon': {
        'WFWorkflowIconStartColor': 4282601983,  # blue
        'WFWorkflowIconGlyphNumber': 59620,
    },
    'WFWorkflowInputContentItemClasses': [],
    'WFWorkflowActions': actions,
    'WFWorkflowTypes': [],
    'WFWorkflowHasOutputFallback': False,
    'WFWorkflowOutputContentItemClasses': [],
    'WFQuickActionSurfaces': [],
    'WFWorkflowHasShortcutInputVariables': False,
}

output = 'rename_photos.shortcut'
with open(output, 'wb') as f:
    plistlib.dump(shortcut_data, f, fmt=plistlib.FMT_BINARY)

print(f'Created: {output}')
print()
print('Transfer to iPhone via:')
print('  • AirDrop')
print('  • iCloud Drive (copy file → open from Files app on iPhone)')
print('  • Email to yourself')
print()
print('On iPhone: tap the file → "Add Shortcut"')
