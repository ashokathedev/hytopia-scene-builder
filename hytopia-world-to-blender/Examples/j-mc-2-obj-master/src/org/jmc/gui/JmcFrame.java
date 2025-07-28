package org.jmc.gui;

import java.awt.GraphicsConfiguration;
import java.awt.HeadlessException;
import java.awt.Toolkit;

import javax.swing.JFrame;

public abstract class JmcFrame extends JFrame {
	

	public JmcFrame() throws HeadlessException {
		super();
		setJmcIcon();
	}

	public JmcFrame(GraphicsConfiguration gc) {
		super(gc);
		setJmcIcon();
	}

	public JmcFrame(String title, GraphicsConfiguration gc) {
		super(title, gc);
		setJmcIcon();
	}

	public JmcFrame(String title) throws HeadlessException {
		super(title);
		setJmcIcon();
	}

	void setJmcIcon() {
		setIconImage(Toolkit.getDefaultToolkit().getImage(MainWindow.class.getResource("/org/jmc/gui/icon.png")));
	}
	
	
	/**
	 * 
	 */
	private static final long serialVersionUID = 8697487349945566606L;

}
