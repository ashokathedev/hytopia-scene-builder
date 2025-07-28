package org.jmc.gui;

import java.awt.Color;
import java.awt.Component;
import java.awt.Dimension;
import java.awt.FlowLayout;
import java.awt.Font;
import java.awt.Insets;
import java.awt.datatransfer.DataFlavor;
import java.awt.datatransfer.UnsupportedFlavorException;
import java.awt.event.ActionEvent;
import java.awt.event.ActionListener;
import java.awt.event.WindowEvent;
import java.awt.event.WindowListener;
import java.io.File;
import java.io.IOException;
import java.util.ArrayList;
import java.util.List;
import java.util.prefs.BackingStoreException;
import java.util.prefs.Preferences;

import javax.imageio.ImageIO;
import javax.swing.*;
import javax.swing.border.TitledBorder;
import javax.swing.event.ChangeEvent;
import javax.swing.event.ChangeListener;
import javax.swing.filechooser.FileFilter;
import javax.swing.filechooser.FileNameExtensionFilter;

import org.jmc.Options;
import org.jmc.registry.Registries;
import org.jmc.util.Filesystem;
import org.jmc.util.IDConvert;
import org.jmc.util.Log;
import org.jmc.util.Messages;
import javax.swing.border.EmptyBorder;

public class Settings extends JmcFrame implements WindowListener, ChangeListener {

	private static final long serialVersionUID = -5546934145954405065L;

	private Preferences prefs;

	JComboBox<String> cbMove, cbSelect, cbLang;
	JTextArea taRestart;
	JSpinner spPrevThreads;
	JmcPackList listPacks;
	JCheckBox chckbxUsePackDefault;
	JLabel lblMinecraftVersion;

	@SuppressWarnings("serial")
	public Settings() {
		prefs = Preferences.userNodeForPackage(getClass());

		setTitle(Messages.getString("Settings.WIN_TITLE"));

		setSize(400, 400);

		JPanel mp = new JPanel();
		getContentPane().add(mp);

		mp.setLayout(new BoxLayout(mp, BoxLayout.PAGE_AXIS));

		String actions[] = { Messages.getString("Settings.Control.LMB"), Messages.getString("Settings.Control.RMB"),
				Messages.getString("Settings.Control.MMB"), Messages.getString("Settings.Control.SLMB"),
				Messages.getString("Settings.Control.SRMB"), Messages.getString("Settings.Control.SMMB") };

		String languages[] = new String[Options.availableLocales.length];
		for (int i = 0; i < languages.length; i++) {
			languages[i] = Options.availableLocales[i].getDisplayLanguage();
		}

		JPanel pMove = new JPanel();
		pMove.setMaximumSize(new Dimension(Short.MAX_VALUE, 50));
		pMove.setLayout(new BoxLayout(pMove, BoxLayout.LINE_AXIS));
		JLabel lMove = new JLabel(Messages.getString("Settings.Control.DRAG"));
		lMove.setBorder(new EmptyBorder(0, 0, 0, 4));
		cbMove = new JComboBox<>(actions);
		pMove.add(lMove);
		pMove.add(cbMove);

		JPanel pSelect = new JPanel();
		pSelect.setMaximumSize(new Dimension(Short.MAX_VALUE, 50));
		pSelect.setLayout(new BoxLayout(pSelect, BoxLayout.LINE_AXIS));
		JLabel lSelect = new JLabel(Messages.getString("Settings.Control.SELECT"));
		lSelect.setBorder(new EmptyBorder(0, 0, 0, 4));
		cbSelect = new JComboBox<>(actions);
		pSelect.add(lSelect);
		pSelect.add(cbSelect);

		JPanel pLang = new JPanel();
		pLang.setMaximumSize(new Dimension(Short.MAX_VALUE, 50));
		pLang.setLayout(new BoxLayout(pLang, BoxLayout.LINE_AXIS));
		JLabel lLang = new JLabel(Messages.getString("Settings.LANGUAGE"));
		lLang.setBorder(new EmptyBorder(0, 0, 0, 4));
		cbLang = new JComboBox<>(languages);
		pLang.add(lLang);
		pLang.add(cbLang);

		JPanel pRestart = new JPanel();
		pRestart.setMaximumSize(new Dimension(Short.MAX_VALUE, 50));
		pRestart.setLayout(new BoxLayout(pRestart, BoxLayout.LINE_AXIS));
		taRestart = new JTextArea(Messages.getString("Settings.RESTART_MSG"));
		taRestart.setLineWrap(true);
		Font fRestart = taRestart.getFont();
		taRestart.setFont(new Font(fRestart.getFamily(), Font.BOLD, 16));
		taRestart.setForeground(Color.red);
		taRestart.setBackground(getBackground());
		taRestart.setVisible(false);
		pRestart.add(taRestart);

		JPanel pButtons = new JPanel();
		pButtons.setMaximumSize(new Dimension(Short.MAX_VALUE, 50));
		pButtons.setLayout(new BoxLayout(pButtons, BoxLayout.LINE_AXIS));
		JButton bReset = new JButton(Messages.getString("Settings.RESTORE"));
		bReset.setMargin(new Insets(2, 10, 2, 10));
		JButton bRestart = new JButton(Messages.getString("Settings.RESTART_BTN"));
		bRestart.setMargin(new Insets(2, 10, 2, 10));
		JButton bReload = new JButton(Messages.getString("Settings.RELOAD_BTN"));
		bReload.setMargin(new Insets(2, 10, 2, 10));
		pButtons.add(bReset);
		pButtons.add(bRestart);
		pButtons.add(bReload);

		bReset.addActionListener(new AbstractAction() {
			@Override
			public void actionPerformed(ActionEvent e) {
				int retval = JOptionPane.showConfirmDialog(Settings.this, Messages.getString("Settings.ARE_YOU_SURE"));
				if (retval == JOptionPane.YES_OPTION)
					resetSettings();
			}
		});

		bRestart.addActionListener(new AbstractAction() {
			@Override
			public void actionPerformed(ActionEvent e) {
				File prog = Filesystem.getProgramExecutable();
				if (prog != null) {
					final ArrayList<String> command = new ArrayList<String>();
					command.add("java");
					command.add("-jar");
					command.add(prog.getPath());

					final ProcessBuilder builder = new ProcessBuilder(command);
					try {
						builder.start();
					} catch (IOException e1) {
						Log.error(Messages.getString("Settings.RESTART_FAIL"), e1, true);
					}
					System.exit(0);
				} else {
					Log.error(Messages.getString("Settings.RESTART_FAIL"), null, true);
				}
			}
		});
		
		bReload.addActionListener(new AbstractAction() {
			@Override
			public void actionPerformed(ActionEvent e) {
				MainWindow.main.stopPreviewLoader();
				IDConvert.initialize();
				Registries.reloadResourcePacks();
				updateMinecraftVerLbl();
				if (MainWindow.main != null) {
					MainWindow.main.reloadPreviewLoader();
				}
			}
		});
		
		AbstractAction saveAction = new AbstractAction() {
			@Override
			public void actionPerformed(ActionEvent e) {
				if (cbMove.getSelectedIndex() == cbSelect.getSelectedIndex()) {
					if (e.getSource().equals(cbMove)) {
						if (cbMove.getSelectedIndex() == 0)
							cbSelect.setSelectedIndex(1);
						else
							cbSelect.setSelectedIndex(0);
					} else {
						if (cbSelect.getSelectedIndex() == 0)
							cbMove.setSelectedIndex(1);
						else
							cbMove.setSelectedIndex(0);
					}
				}
				saveSettings();
			}
		};

		mp.add(pMove);
		mp.add(pSelect);
		mp.add(pLang);
		
		JPanel pPrevThreads = new JPanel();
		pPrevThreads.setMaximumSize(new Dimension(32767, 50));
		mp.add(pPrevThreads);
		pPrevThreads.setLayout(new FlowLayout(FlowLayout.LEFT, 0, 0));
		
		JLabel lPrevThreads = new JLabel(Messages.getString("Settings.PREVIEW_THREADS"));
		lPrevThreads.setBorder(new EmptyBorder(0, 0, 0, 4));
		pPrevThreads.add(lPrevThreads);
		
		spPrevThreads = new JSpinner();
		spPrevThreads.setModel(new SpinnerNumberModel(8, 1, 512, 1));
		pPrevThreads.add(spPrevThreads);
		
		JPanel pResourcePacks = new JPanel();
		pResourcePacks.setBorder(new TitledBorder(null, Messages.getString("Settings.ResourcePack.HEADER"), TitledBorder.LEFT, TitledBorder.TOP, null, null));
		mp.add(pResourcePacks);
		pResourcePacks.setLayout(new BoxLayout(pResourcePacks, BoxLayout.Y_AXIS));
		
		JPanel pPackList = new JPanel();
		pResourcePacks.add(pPackList);
		pPackList.setLayout(new BoxLayout(pPackList, BoxLayout.X_AXIS));
		
		JScrollPane scrollListPacks = new JScrollPane();
		pPackList.add(scrollListPacks);
		scrollListPacks.setVerticalScrollBarPolicy(ScrollPaneConstants.VERTICAL_SCROLLBAR_ALWAYS);
		
		listPacks = new JmcPackList();
		listPacks.setVisibleRowCount(5);
		listPacks.setBackground(Color.WHITE);
		listPacks.setSelectionMode(ListSelectionModel.SINGLE_SELECTION);
		scrollListPacks.setViewportView(listPacks);
		scrollListPacks.setTransferHandler(new TransferHandler(null) {
			@Override
			public boolean canImport(TransferSupport support) {
				if (support.isDataFlavorSupported(DataFlavor.javaFileListFlavor)) {
					if ((support.getSourceDropActions() & LINK) != 0)
						support.setDropAction(LINK);
					return true;
				}
				return false;
			}
			@SuppressWarnings("unchecked")
			@Override
			public boolean importData(TransferSupport support) {
				if (!canImport(support)) {
					return false;
				}
				List<File> files;
				try {
					files = (List<File>) support.getTransferable().getTransferData(DataFlavor.javaFileListFlavor);
				} catch (UnsupportedFlavorException | IOException ex) {
					return false;
				}
				
				for (File file: files) {
					listPacks.getModel().add(0, file);
				}
				listPacks.setSelectedIndex(0);
				saveSettings();
				updateResourcePacks(true);
				return true;
			}
		});
		
		JPanel pPackListButtons = new JPanel();
		pPackList.add(pPackListButtons);
		pPackListButtons.setLayout(new BoxLayout(pPackListButtons, BoxLayout.Y_AXIS));
		
		
		ImageIcon iconPackAdd, iconPackRemove, iconPackUp, iconPackDown;
		iconPackAdd = iconPackRemove = iconPackUp = iconPackDown = null;
		try {
			iconPackAdd = new ImageIcon(ImageIO.read(getClass().getResourceAsStream("/org/jmc/gui/packAdd.png")));
			iconPackRemove = new ImageIcon(ImageIO.read(getClass().getResourceAsStream("/org/jmc/gui/packRemove.png")));
			iconPackUp = new ImageIcon(ImageIO.read(getClass().getResourceAsStream("/org/jmc/gui/packUp.png")));
			iconPackDown = new ImageIcon(ImageIO.read(getClass().getResourceAsStream("/org/jmc/gui/packDown.png")));
		} catch (IOException | IllegalArgumentException e) {
			Log.error("Couldn't load settings icons!", e);
		}
		
		JButton btnPackAdd = new JButton(iconPackAdd);
		btnPackAdd.setAlignmentX(Component.CENTER_ALIGNMENT);
		btnPackAdd.setToolTipText(Messages.getString("Settings.ResourcePack.ADD"));
		btnPackAdd.setMargin(new Insets(2, 2, 2, 2));
		btnPackAdd.addActionListener(new ActionListener() {
			public void actionPerformed(ActionEvent e) {
				JFileChooser jfc = new JFileChooser(MainWindow.settings.getLastExportPath());
				// Only files currently supported, uncomment when support for directories is added
				//jfc.setFileSelectionMode(JFileChooser.FILES_AND_DIRECTORIES);
				jfc.setFileHidingEnabled(false);
				jfc.setMultiSelectionEnabled(true);
				jfc.addChoosableFileFilter(new FileFilter() {
					@Override public String getDescription() {return "Extracted pack.mcmeta";}
					@Override public boolean accept(File f) {return f.isDirectory() || f.getName().equals("pack.mcmeta");}
				});
				jfc.setFileFilter(new FileNameExtensionFilter("Zip & Jar files", "zip", "ZIP", "Zip", "jar", "JAR", "Jar"));
				jfc.setCurrentDirectory(Filesystem.getMinecraftDir());
				jfc.showDialog(Settings.this, Messages.getString("ExportOptions.Textures.SEL_RP"));

				DefaultListModel<File> listPacksModel = listPacks.getModel();
				File[] selectedFiles = jfc.getSelectedFiles();

				for (File selectedFile : selectedFiles) {
					if (selectedFile == null) {
						return;
					}

					listPacksModel.add(0, selectedFile);
				}

				listPacks.setSelectedIndex(0);
				saveSettings();
				updateResourcePacks(true);
			}
		});
		pPackListButtons.add(btnPackAdd);
		
		JButton btnPackRemove = new JButton(iconPackRemove);
		btnPackRemove.setAlignmentX(Component.CENTER_ALIGNMENT);
		btnPackRemove.setToolTipText(Messages.getString("Settings.ResourcePack.REMOVE"));
		btnPackRemove.setMargin(new Insets(2, 2, 2, 2));
		btnPackRemove.addActionListener(new ActionListener() {
			public void actionPerformed(ActionEvent e) {
				if (listPacks.removeSelected()) {
					saveSettings();
					updateResourcePacks(true);
				}
			}
		});
		pPackListButtons.add(btnPackRemove);
		
		JButton btnPackUp = new JButton(iconPackUp);
		btnPackUp.setAlignmentX(Component.CENTER_ALIGNMENT);
		btnPackUp.setToolTipText(Messages.getString("Settings.ResourcePack.UP"));
		btnPackUp.setMargin(new Insets(2, 2, 2, 2));
		btnPackUp.addActionListener(new ActionListener() {
			public void actionPerformed(ActionEvent e) {
				if (listPacks.moveSelectedUp()) {
					saveSettings();
					updateResourcePacks(true);
				}
			}
		});
		pPackListButtons.add(btnPackUp);
		
		JButton btnPackDown = new JButton(iconPackDown);
		btnPackDown.setAlignmentX(Component.CENTER_ALIGNMENT);
		btnPackDown.setToolTipText(Messages.getString("Settings.ResourcePack.DOWN"));
		btnPackDown.setMargin(new Insets(2, 2, 2, 2));
		btnPackDown.addActionListener(new ActionListener() {
			public void actionPerformed(ActionEvent e) {
				if (listPacks.moveSelectedDown()) {
					saveSettings();
					updateResourcePacks(true);
				}
			}
		});
		pPackListButtons.add(btnPackDown);
		
		JPanel pUsePackDefault = new JPanel();
		pResourcePacks.add(pUsePackDefault);
		pUsePackDefault.setLayout(new BoxLayout(pUsePackDefault, BoxLayout.X_AXIS));
		
		chckbxUsePackDefault = new JCheckBox(Messages.getString("Settings.ResourcePack.USE_DEFAULT"));
		chckbxUsePackDefault.setAlignmentX(Component.CENTER_ALIGNMENT);
		chckbxUsePackDefault.setSelected(true);
		chckbxUsePackDefault.addActionListener(new ActionListener() {
			@Override
			public void actionPerformed(ActionEvent e) {
				saveSettings();
				updateResourcePacks(true);
			}
		});
		pUsePackDefault.add(chckbxUsePackDefault);
		pUsePackDefault.add(new JSeparator(SwingConstants.VERTICAL)).setMaximumSize(new Dimension(6, 16));
		lblMinecraftVersion = new JLabel(Messages.getString("Settings.ResourcePack.NO_MC_VERSION"));
		pUsePackDefault.add(lblMinecraftVersion);
		
		
		mp.add(pRestart);
		mp.add(pButtons);

		mp.setBorder(BorderFactory.createEmptyBorder(10, 10, 10, 10));
		
		pack();
		setMinimumSize(getSize());

		loadSettings();
		updateResourcePacks(false);

		addWindowListener(this);
		cbMove.addActionListener(saveAction);
		cbSelect.addActionListener(saveAction);
		cbLang.addActionListener(saveAction);
		spPrevThreads.addChangeListener(new ChangeListener() {
			@Override
			public void stateChanged(ChangeEvent e) {
				saveSettings();
				MainWindow.main.reloadPreviewLoader();
			}
		});
	}

	public Preferences getPreferences() {
		return prefs;
	}

	public void setLastLoadedMap(String path) {
		prefs.put("LAST_MAP", path);
	}

	public String getLastLoadedMap() {
		return prefs.get("LAST_MAP", ""); //$NON-NLS-2$
	}

	public void setLastExportPath(String path) {
		prefs.put("LAST_EXPORT_PATH", path);
	}

	public String getLastExportPath() {
		File cwd = new File(".");
		String str = "";
		try {
			str = cwd.getCanonicalPath();
		} catch (Exception e) {
		}
		return prefs.get("LAST_EXPORT_PATH", str);
	}

	public void setLastVisitedDir(String path) {
		prefs.put("LAST_VISITED_DIR", path);
	}

	public String getLastVisitedDir() {
		return prefs.get("LAST_VISITED_DIR", getLastExportPath());
	}

	public int getMoveAction() {
		return cbMove.getSelectedIndex();
	}

	public int getSelectAction() {
		return cbSelect.getSelectedIndex();
	}

	private void loadSettings() {
		try {
			cbMove.setSelectedIndex(prefs.getInt("MOVE_ACTION", 1));
			cbSelect.setSelectedIndex(prefs.getInt("SELECT_ACTION", 0));
			cbLang.setSelectedIndex(prefs.getInt("LANGUAGE", 0));
			spPrevThreads.setValue(prefs.getInt("PREVIEW_THREADS", 8));
			listPacks.loadPrefString(prefs.get("RESOURCE_PACKS", "[]"));
			chckbxUsePackDefault.setSelected(prefs.getBoolean("USE_DEFAULT_RESOURCE_PACK", true));
		} catch (IllegalArgumentException e) {
			Log.error("Error loading settings! Resetting...", e);
			resetSettings();
		}
	}

	private void saveSettings() {
		taRestart.setVisible(false);

		prefs.putInt("MOVE_ACTION", cbMove.getSelectedIndex());
		prefs.putInt("SELECT_ACTION", cbSelect.getSelectedIndex());
		prefs.putInt("PREVIEW_THREADS", (Integer) spPrevThreads.getValue());
		int l = prefs.getInt("LANGUAGE", 0);
		if (cbLang.getSelectedIndex() != l) {
			prefs.putInt("LANGUAGE", cbLang.getSelectedIndex());
			taRestart.setVisible(true);
		}
		try {
			prefs.put("RESOURCE_PACKS", listPacks.getPrefString());
		} catch (IllegalArgumentException e) {
			Log.error("Resource pack list could not be saved!", e);
		}
		prefs.putBoolean("USE_DEFAULT_RESOURCE_PACK", chckbxUsePackDefault.isSelected());
	}

	private void resetSettings() {
		try {
			prefs.clear();
			cbMove.setSelectedIndex(1);
			cbSelect.setSelectedIndex(0);
			cbLang.setSelectedIndex(0);
			spPrevThreads.setValue(8);
			listPacks.reset();
			chckbxUsePackDefault.setSelected(true);
		} catch (BackingStoreException e) {
		}
		saveSettings();
	}
	
	private void updateResourcePacks(boolean reloadRegistries) {
		List<File> resPacks = Options.resourcePacks;
		synchronized (resPacks) {
			resPacks.clear();
			for (File pack : listPacks.getList()) {
				resPacks.add(pack);
			}
			if (chckbxUsePackDefault.isSelected()) {
				File mc = Filesystem.getMinecraftJar();
				if (mc != null) {
					Log.info(String.format("Using minecraft %s as default resource pack.", mc.getName()));
					resPacks.add(mc);
				} else {
					Log.info("No minecraft .jar found to use as default resource pack!");
				}
			}
		}
		updateMinecraftVerLbl();
		if (reloadRegistries) {
			Registries.reloadResourcePacks();
			if (MainWindow.main != null) {
				MainWindow.main.reloadPreviewLoader();
			}
		}
	}
	
	private void updateMinecraftVerLbl() {
		File mcJar = Filesystem.getMinecraftJar();
		String mcVer = Messages.getString("Settings.ResourcePack.NO_MC_VERSION");
		if (mcJar != null) {
			mcVer = mcJar.getName().toLowerCase().replace(".jar", "");
		}
		lblMinecraftVersion.setText(mcVer);
	}

	@Override
	public void windowActivated(WindowEvent e) {
		loadSettings();
	}

	@Override
	public void windowClosed(WindowEvent e) {
	}

	@Override
	public void windowClosing(WindowEvent e) {
		saveSettings();
	}

	@Override
	public void windowDeactivated(WindowEvent e) {
		saveSettings();
	}

	@Override
	public void windowDeiconified(WindowEvent e) {
	}

	@Override
	public void windowIconified(WindowEvent e) {
	}

	@Override
	public void windowOpened(WindowEvent e) {
	}

	@Override
	public void stateChanged(ChangeEvent e) {
		saveSettings();

	}
}
